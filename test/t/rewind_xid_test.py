#!/usr/bin/env python3
# coding: utf-8

import unittest
import testgres
import time
import re
import os

from .base_test import BaseTest
from .base_test import generate_string
from testgres.enums import NodeStatus
from testgres.exceptions import StartNodeException, QueryException

import string
import random


class RewindXidTest(BaseTest):

	# Small tests:
	# test_rewind_xid_oriole
	# test_rewind_xid_heap
	# test_rewind_xid_heap_subxids
	# test_rewind_xid               // oriole+heap
	# test_rewind_xid_subxids       // oriole+heap

	# DDL tests :
	# test_rewind_xid_ddl_create    // oriole+heap
	# test_rewind_xid_ddl_drop      // oriole+heap
	# test_rewind_xid_ddl_truncate  // oriole+heap
	# test_rewind_xid_ddl_rewrite   // oriole+heap

	# Small scale tests

	def test_rewind_xid_oriole(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 500\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING orioledb;\n")

		for i in range(1, 6):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		a, *b = (node.execute('postgres',
		                      'select orioledb_get_current_oxid();\n'))[0]
		oxid = int(a)
		#		print(oxid)
		invalidxid = 0

		for i in range(6, 20):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		node.safe_psql(
		    'postgres', "select orioledb_rewind_to_transaction(%d,%ld);\n" %
		    (invalidxid, oxid))
		time.sleep(1)

		node.is_started = False
		node.start()

		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)
		node.stop()

	def test_rewind_xid_heap(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 500\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test_heap (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 6):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)
		invalidoxid = 9223372036854775807

		for i in range(6, 20):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

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

	def test_rewind_xid_heap_subxids(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 500\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test_heap (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 25, 4):
			node.safe_psql(
			    'postgres',
			    "BEGIN; INSERT INTO o_test_heap VALUES (%d, %d || 'val'); SAVEPOINT sp1;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val'); SAVEPOINT sp2;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val'); SAVEPOINT sp3;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val'); COMMIT;\n" %
			    (i, i, i + 1, i + 1, i + 2, i + 2, i + 3, i + 3))

		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)
		invalidoxid = 9223372036854775807

		for i in range(25, 80, 4):
			node.safe_psql(
			    'postgres',
			    "BEGIN; INSERT INTO o_test_heap VALUES (%d, %d || 'val'); SAVEPOINT sp1;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val'); SAVEPOINT sp2;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val'); SAVEPOINT sp3;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val'); COMMIT;\n" %
			    (i, i, i + 1, i + 1, i + 2, i + 2, i + 3, i + 3))

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

	def test_rewind_xid(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 500\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test_heap (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 6):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		a, *b = (node.execute('postgres',
		                      'select orioledb_get_current_oxid();\n'))[0]
		oxid = int(a)
		#		print(oxid)
		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)

		for i in range(6, 20):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		node.safe_psql(
		    'postgres',
		    "select orioledb_rewind_to_transaction(%d,%ld);\n" % (xid, oxid))
		time.sleep(1)

		node.is_started = False
		node.start()

		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)
		node.stop()

	def test_rewind_xid_subxids(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 500\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test_heap (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 25, 4):
			node.safe_psql(
			    'postgres',
			    "BEGIN; INSERT INTO o_test_heap VALUES (%d, %d || 'val');\n"
			    "INSERT INTO o_test VALUES (%d, %d || 'val'); SAVEPOINT sp1;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val');\n"
			    "INSERT INTO o_test VALUES (%d, %d || 'val'); SAVEPOINT sp2;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val');\n"
			    "INSERT INTO o_test VALUES (%d, %d || 'val'); SAVEPOINT sp3;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val');\n"
			    "INSERT INTO o_test VALUES (%d, %d || 'val'); COMMIT;\n" %
			    (i, i, i, i, i + 1, i + 1, i + 1, i + 1, i + 2, i + 2, i + 2,
			     i + 2, i + 3, i + 3, i + 3, i + 3))

		a, *b = (node.execute('postgres',
		                      'select orioledb_get_current_oxid();\n'))[0]
		oxid = int(a)
		#		print(oxid)
		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)

		for i in range(25, 80, 4):
			node.safe_psql(
			    'postgres',
			    "BEGIN; INSERT INTO o_test_heap VALUES (%d, %d || 'val');\n"
			    "INSERT INTO o_test VALUES (%d, %d || 'val'); SAVEPOINT sp1;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val');\n"
			    "INSERT INTO o_test VALUES (%d, %d || 'val'); SAVEPOINT sp2;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val');\n"
			    "INSERT INTO o_test VALUES (%d, %d || 'val'); SAVEPOINT sp3;\n"
			    "INSERT INTO o_test_heap VALUES (%d, %d || 'val');\n"
			    "INSERT INTO o_test VALUES (%d, %d || 'val'); COMMIT;\n" %
			    (i, i, i, i, i + 1, i + 1, i + 1, i + 1, i + 2, i + 2, i + 2,
			     i + 2, i + 3, i + 3, i + 3, i + 3))

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
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val'), (6, '6val'), (7, '7val'), (8, '8val'), (9, '9val'), (10, '10val'), (11, '11val'), (12, '12val'), (13, '13val'), (14, '14val'), (15, '15val'), (16, '16val'), (17, '17val'), (18, '18val'), (19, '19val'), (20, '20val'), (21, '21val'), (22, '22val'), (23, '23val'), (24, '24val')]"
		)
		node.stop()


# DDL tests

	def test_rewind_xid_ddl_create(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 500\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test_heap (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 6):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		a, *b = (node.execute('postgres',
		                      'select orioledb_get_current_oxid();\n'))[0]
		oxid = int(a)
		#		print(oxid)
		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)

		node.safe_psql(
		    'postgres', "CREATE TABLE o_test_ddl (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE o_test_heap_ddl (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(6, 20):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		node.safe_psql(
		    'postgres',
		    "select orioledb_rewind_to_transaction(%d,%ld);\n" % (xid, oxid))
		time.sleep(1)

		node.is_started = False
		node.start()

		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)

		with self.assertRaises(QueryException) as e:
			node.safe_psql('postgres', 'SELECT * FROM o_test_ddl;')
		self.assertIn('ERROR:  relation "o_test_ddl" does not exist',
		              self.stripErrorMsg(e.exception.message).rstrip("\r\n"))
		with self.assertRaises(QueryException) as e:
			node.safe_psql('postgres', 'SELECT * FROM o_test_heap_ddl;')
		self.assertIn('ERROR:  relation "o_test_heap_ddl" does not exist',
		              self.stripErrorMsg(e.exception.message).rstrip("\r\n"))
		node.stop()

	def test_rewind_xid_ddl_drop(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 500\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE IF NOT EXISTS o_test_heap (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE o_test_ddl (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE o_test_heap_ddl (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 6):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		a, *b = (node.execute('postgres',
		                      'select orioledb_get_current_oxid();\n'))[0]
		oxid = int(a)
		#		print(oxid)
		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)

		for i in range(6, 20):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		node.safe_psql('postgres', "DROP TABLE o_test_heap_ddl;\n")
		node.safe_psql('postgres', "DROP TABLE o_test_ddl;\n")

		node.safe_psql(
		    'postgres',
		    "select orioledb_rewind_to_transaction(%d,%ld);\n" % (xid, oxid))
		time.sleep(1)

		node.is_started = False
		node.start()

		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_ddl;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap_ddl;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)

		node.stop()

	def test_rewind_xid_ddl_truncate(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 500\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE o_test_ddl (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE o_test_heap_ddl (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 6):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		a, *b = (node.execute('postgres',
		                      'select orioledb_get_current_oxid();\n'))[0]
		oxid = int(a)
		#		print(oxid)
		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)

		node.safe_psql('postgres', "TRUNCATE TABLE o_test_ddl;")
		node.safe_psql('postgres', "TRUNCATE TABLE o_test_heap_ddl;")

		for i in range(6, 20):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		node.safe_psql(
		    'postgres',
		    "select orioledb_rewind_to_transaction(%d,%ld);\n" % (xid, oxid))
		time.sleep(1)

		node.is_started = False
		node.start()

		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_ddl;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap_ddl;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)

		node.stop()

	def test_rewind_xid_ddl_rewrite(self):
		node = self.node
		node.append_conf(
		    'postgresql.conf', "orioledb.rewind_max_time = 500\n"
		    "orioledb.enable_rewind = true\n"
		    "orioledb.rewind_buffers = 6\n")
		node.start()

		node.safe_psql('postgres',
		               "CREATE EXTENSION IF NOT EXISTS orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE o_test_ddl (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING orioledb;\n")

		node.safe_psql(
		    'postgres', "CREATE TABLE o_test_heap_ddl (\n"
		    "	id integer NOT NULL,\n"
		    "	val text,\n"
		    "	PRIMARY KEY (id)\n"
		    ") USING heap;\n")

		for i in range(1, 6):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		a, *b = (node.execute('postgres',
		                      'select orioledb_get_current_oxid();\n'))[0]
		oxid = int(a)
		#		print(oxid)
		a, *b = (node.execute('postgres', 'select pg_current_xact_id();\n'))[0]
		xid = int(a)
		#		print(xid)

		node.safe_psql('postgres',
		               "ALTER TABLE o_test_ddl ALTER COLUMN id TYPE real;")
		node.safe_psql(
		    'postgres',
		    "ALTER TABLE o_test_heap_ddl ALTER COLUMN id TYPE real;")

		for i in range(6, 11):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_ddl;')),
		    "[(1.0, '1val'), (2.0, '2val'), (3.0, '3val'), (4.0, '4val'), (5.0, '5val'), (6.0, '6val'), (7.0, '7val'), (8.0, '8val'), (9.0, '9val'), (10.0, '10val')]"
		)
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap_ddl;')),
		    "[(1.0, '1val'), (2.0, '2val'), (3.0, '3val'), (4.0, '4val'), (5.0, '5val'), (6.0, '6val'), (7.0, '7val'), (8.0, '8val'), (9.0, '9val'), (10.0, '10val')]"
		)

		for i in range(11, 20):
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))
			node.safe_psql(
			    'postgres', "INSERT INTO o_test_heap_ddl\n"
			    "	VALUES (%d, %d || 'val');\n" % (i, i))

		node.safe_psql(
		    'postgres',
		    "select orioledb_rewind_to_transaction(%d,%ld);\n" % (xid, oxid))
		time.sleep(1)

		node.is_started = False
		node.start()

		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_ddl;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)
		self.assertEqual(
		    str(node.execute('postgres', 'SELECT * FROM o_test_heap_ddl;')),
		    "[(1, '1val'), (2, '2val'), (3, '3val'), (4, '4val'), (5, '5val')]"
		)

		node.stop()
