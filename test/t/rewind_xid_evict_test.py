#!/usr/bin/env python3
# coding: utf-8

import unittest
import testgres
import time
import re
import os
import sys

from .base_test import BaseTest
from .base_test import generate_string
from testgres.enums import NodeStatus
from testgres.exceptions import StartNodeException, QueryException

import string
import random
import tempfile


class RewindXidTest(BaseTest):

	# Evict tests:
	# test_rewind_xid_oriole_evict
	# test_rewind_xid_heap_evict
	# test_rewind_xid_evict         // oriole+heap
	# test_rewind_xid_heap_evict_subxids
	# test_rewind_xid_evict_subxids // oriole+heap

	# Number of xids to rewind in each test should be more than (3/2)*orioledb.rewind_buffers*(8192/sizeof(rewindItem)))
	# Multiplier of (3/2) allows DiskEvicted to be more or equal to than each of in-memory buffers (addBuffer and completeBuffer).
	# 8192/sizeof(rewindItem) currently = 68

	# Tests with eviction: medium scale (suitable for Valgrind)

	def test_rewind_xid_oriole_evict(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 5000\n"
		    "orioledb.rewind_max_transactions 1000000\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test (\n"
		    "	val text\n"
		    ") USING orioledb;\n")

		for i in range(1, 6):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test\n"
			    "	VALUES (%d || 'val');\n" % (i, ))

		a, *b = (node.execute('postgres',
		                      'select orioledb_get_current_oxid();\n'))[0]
		oxid = int(a)
		#		print(oxid)
		invalidxid = 0

		fp = tempfile.NamedTemporaryFile(mode='wt', delete_on_close=False)
		fp.write("INSERT INTO o_test (val) VALUES ('newval!');\n")
		fp.close()
		node.pgbench_with_wait(options=[
		    '-M', 'prepared', '-f', fp.name, '-n', '-c', '4', '-j', '4', '-t',
		    '161'
		],
		                       stderr=sys.stderr)

		a, *b = (node.execute(
		    'postgres', 'select orioledb_get_rewind_queue_length();\n'))[0]
		len = int(a)
		c, *b = (node.execute(
		    'postgres', 'select orioledb_get_rewind_evicted_length();\n'))[0]
		ev = int(c)
		#		print(len, ev, len - ev)

		node.safe_psql(
		    'postgres', "select orioledb_rewind_to_transaction(%d,%ld);\n" %
		    (invalidxid, oxid))
		time.sleep(1)

		node.is_started = False
		node.start()

		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test;')),
		    "[('1val',), ('2val',), ('3val',), ('4val',), ('5val',)]")

		node.stop()

	def test_rewind_xid_heap_evict(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 5000\n"
		    "orioledb.rewind_max_transactions 1000000\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test_heap (\n"
		    "	id serial NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 6):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap (val)\n"
			    "	VALUES (%d || 'val');\n" % (i, ))

		invalidoxid = 9223372036854775807
		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)

		fp = tempfile.NamedTemporaryFile(mode='wt', delete_on_close=False)
		fp.write("INSERT INTO o_test_heap (val) VALUES ('newval!');\n")
		fp.close()
		node.pgbench_with_wait(options=[
		    '-M', 'prepared', '-f', fp.name, '-n', '-c', '4', '-j', '4', '-t',
		    '161'
		],
		                       stderr=sys.stderr)

		a, *b = (node.execute(
		    'postgres', 'select orioledb_get_rewind_queue_length();\n'))[0]
		len = int(a)
		c, *b = (node.execute(
		    'postgres', 'select orioledb_get_rewind_evicted_length();\n'))[0]
		ev = int(c)
		#		print(len, ev, len - ev)

		node.safe_psql(
		    'postgres', "select orioledb_rewind_to_transaction(%d,%ld);\n" %
		    (xid, invalidoxid))
		time.sleep(1)

		node.is_started = False
		node.start()

		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)

		node.stop()

	def test_rewind_xid_evict(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 5000\n"
		    "orioledb.rewind_max_transactions 1000000\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test (\n"
		    "	val text\n"
		    ") USING orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test_heap (\n"
		    "	id serial NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 6):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test (val)\n"
			    "	VALUES (%d || 'val');\n" % (i, ))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap (val)\n"
			    "	VALUES (%d || 'val');\n" % (i, ))

		a, *b = (node.execute('postgres',
		                      'select orioledb_get_current_oxid();\n'))[0]
		oxid = int(a)
		#		print(oxid)
		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)

		fp = tempfile.NamedTemporaryFile(mode='wt', delete_on_close=False)
		fp.write("INSERT INTO o_test (val) VALUES ('newval!');\n")
		fp.write("INSERT INTO o_test_heap (val) VALUES ('newval!');\n")
		fp.close()
		node.pgbench_with_wait(options=[
		    '-M', 'prepared', '-f', fp.name, '-n', '-c', '4', '-j', '4', '-t',
		    '2500'
		],
		                       stderr=sys.stderr)

		a, *b = (node.execute(
		    'postgres', 'select orioledb_get_rewind_queue_length();\n'))[0]
		len = int(a)
		c, *b = (node.execute(
		    'postgres', 'select orioledb_get_rewind_evicted_length();\n'))[0]
		ev = int(c)
		#		print(len, ev, len - ev)

		node.safe_psql(
		    'postgres',
		    "select orioledb_rewind_to_transaction(%d,%ld);\n" % (xid, oxid))
		time.sleep(1)

		node.is_started = False
		node.start()

		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test;')),
		    "[('1val',), ('2val',), ('3val',), ('4val',), ('5val',)]")
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)
		node.stop()

	def test_rewind_xid_heap_evict_subxids(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 5000\n"
		    "orioledb.rewind_max_transactions 1000000\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test_heap (\n"
		    "	id serial NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		fp = tempfile.NamedTemporaryFile(mode='wt', delete_on_close=False)
		fp.write("BEGIN;\n")
		fp.write("INSERT INTO o_test_heap (val) VALUES ('newval!');\n")
		fp.write("SAVEPOINT sp1;\n")
		fp.write("INSERT INTO o_test_heap (val) VALUES ('newval!');\n")
		fp.write("SAVEPOINT sp2;\n")
		fp.write("INSERT INTO o_test_heap (val) VALUES ('newval!');\n")
		fp.write("SAVEPOINT sp3;\n")
		fp.write("INSERT INTO o_test_heap (val) VALUES ('newval!');\n")
		fp.write("COMMIT;\n")
		fp.close()

		for i in range(1, 25, 4):
			node.safe_psql(
			    'postgres',
			    "BEGIN; INSERT INTO o_test_heap (val) VALUES (%d || 'val'); SAVEPOINT sp1;\n"
			    "INSERT INTO o_test_heap (val) VALUES (%d || 'val'); SAVEPOINT sp2;\n"
			    "INSERT INTO o_test_heap (val) VALUES (%d || 'val'); SAVEPOINT sp3;\n"
			    "INSERT INTO o_test_heap (val) VALUES (%d || 'val'); COMMIT;\n"
			    % (i, i + 1, i + 2, i + 3))

		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)
		invalidoxid = 9223372036854775807

		node.pgbench_with_wait(options=[
		    '-M', 'prepared', '-f', fp.name, '-n', '-c', '4', '-j', '4', '-t',
		    '161'
		],
		                       stderr=sys.stderr)

		a, *b = (node.execute(
		    'postgres', 'select orioledb_get_rewind_queue_length();\n'))[0]
		len = int(a)
		c, *b = (node.execute(
		    'postgres', 'select orioledb_get_rewind_evicted_length();\n'))[0]
		ev = int(c)
		#		print(len, ev, len - ev)

		node.safe_psql(
		    'postgres', "select orioledb_rewind_to_transaction(%d,%ld);\n" %
		    (xid, invalidoxid))
		time.sleep(1)
		node.is_started = False
		node.start()

		self.maxDiff = None
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val'), (6, '6val'), (7, '7val'), (8, '8val'), (9, '9val'), (10, '10val'), (11, '11val'), (12, '12val'), (13, '13val'), (14, '14val'), (15, '15val'), (16, '16val'), (17, '17val'), (18, '18val'), (19, '19val'), (20, '20val'), (21, '21val'), (22, '22val'), (23, '23val'), (24, '24val')]"
		)
		node.stop()

	def test_rewind_xid_evict_subxids(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 5000\n"
		    "orioledb.rewind_max_transactions 1000000\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test (\n"
		    "	val text\n"
		    ") USING orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test_heap (\n"
		    "	id serial NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 25, 4):
			node.safe_psql(
			    'postgres',
			    "BEGIN; INSERT INTO o_test_heap (val) VALUES (%d || 'val');\n"
			    "INSERT INTO o_test (val) VALUES (%d || 'val'); SAVEPOINT sp1;\n"
			    "INSERT INTO o_test_heap (val) VALUES (%d || 'val');\n"
			    "INSERT INTO o_test (val) VALUES (%d || 'val'); SAVEPOINT sp2;\n"
			    "INSERT INTO o_test_heap (val) VALUES (%d || 'val');\n"
			    "INSERT INTO o_test (val) VALUES (%d || 'val'); SAVEPOINT sp3;\n"
			    "INSERT INTO o_test_heap (val) VALUES (%d || 'val');\n"
			    "INSERT INTO o_test (val) VALUES (%d || 'val'); COMMIT;\n" %
			    (i, i, i + 1, i + 1, i + 2, i + 2, i + 3, i + 3))

		a, *b = (node.execute('postgres',
		                      'select orioledb_get_current_oxid();\n'))[0]
		oxid = int(a)
		#		print(oxid)
		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)

		fp = tempfile.NamedTemporaryFile(mode='wt', delete_on_close=False)
		fp.write("BEGIN;\n")
		fp.write("INSERT INTO o_test_heap (val) VALUES ('newval!');\n")
		fp.write("INSERT INTO o_test (val) VALUES ('newval!');\n")
		fp.write("SAVEPOINT sp1;\n")
		fp.write("INSERT INTO o_test_heap (val) VALUES ('newval!');\n")
		fp.write("INSERT INTO o_test (val) VALUES ('newval!');\n")
		fp.write("SAVEPOINT sp2;\n")
		fp.write("INSERT INTO o_test_heap (val) VALUES ('newval!');\n")
		fp.write("INSERT INTO o_test (val) VALUES ('newval!');\n")
		fp.write("SAVEPOINT sp3;\n")
		fp.write("INSERT INTO o_test_heap (val) VALUES ('newval!');\n")
		fp.write("INSERT INTO o_test (val) VALUES ('newval!');\n")
		fp.write("COMMIT;\n")
		fp.close()
		node.pgbench_with_wait(options=[
		    '-M', 'prepared', '-f', fp.name, '-n', '-c', '4', '-j', '4', '-t',
		    '161'
		],
		                       stderr=sys.stderr)

		a, *b = (node.execute(
		    'postgres', 'select orioledb_get_rewind_queue_length();\n'))[0]
		len = int(a)
		c, *b = (node.execute(
		    'postgres', 'select orioledb_get_rewind_evicted_length();\n'))[0]
		ev = int(c)
		#		print(len, ev, len - ev)

		node.safe_psql(
		    'postgres',
		    "select orioledb_rewind_to_transaction(%d,%ld);\n" % (xid, oxid))

		time.sleep(1)
		node.is_started = False
		node.start()

		self.maxDiff = None
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val'), (6, '6val'), (7, '7val'), (8, '8val'), (9, '9val'), (10, '10val'), (11, '11val'), (12, '12val'), (13, '13val'), (14, '14val'), (15, '15val'), (16, '16val'), (17, '17val'), (18, '18val'), (19, '19val'), (20, '20val'), (21, '21val'), (22, '22val'), (23, '23val'), (24, '24val')]"
		)
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test;')),
		    "[('1val',), ('2val',), ('3val',), ('4val',), ('5val',), ('6val',), ('7val',), ('8val',), ('9val',), ('10val',), ('11val',), ('12val',), ('13val',), ('14val',), ('15val',), ('16val',), ('17val',), ('18val',), ('19val',), ('20val',), ('21val',), ('22val',), ('23val',), ('24val',)]"
		)
		node.stop()
