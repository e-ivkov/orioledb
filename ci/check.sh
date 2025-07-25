#!/bin/bash

set -eu
export PATH="$GITHUB_WORKSPACE/pgsql/bin:$GITHUB_WORKSPACE/python3-venv/bin:$PATH"

# unsets limit for coredumps size
ulimit -c unlimited -S
# sets a coredump file pattern
mkdir -p /tmp/cores-$GITHUB_SHA-$TIMESTAMP
sudo sh -c "echo \"/tmp/cores-$GITHUB_SHA-$TIMESTAMP/%t_%p.core\" > /proc/sys/kernel/core_pattern"

# remember number of oom-killer visits in syslog before test
[ -f /var/log/system.log ] && syslogfile=/var/log/system.log || syslogfile=/var/log/syslog
[ -f $syslogfile ] && cat $syslogfile | grep oom-kill | wc -l > ./ooms.tmp \
					|| { echo "Syslog file not found"; status=1; }


status=0

cd orioledb
if [ $CHECK_TYPE = "valgrind_1" ]; then
	make USE_PGXS=1 IS_DEV=1 VALGRIND=1 regresscheck isolationcheck testgrescheck_part_1 -j $(nproc) || status=$?
elif [ $CHECK_TYPE = "valgrind_2" ]; then
	make USE_PGXS=1 IS_DEV=1 VALGRIND=1 testgrescheck_part_2 -j $(nproc) || status=$?
elif [ $CHECK_TYPE = "valgrind_3" ]; then
	make USE_PGXS=1 IS_DEV=1 VALGRIND=1 testgrescheck_part_3 -j $(nproc) || status=$?
elif [ $CHECK_TYPE = "sanitize" ]; then
	UBSAN_OPTIONS="log_path=$PWD/ubsan.log" \
	ASAN_OPTIONS=$(cat <<-END
		verify_asan_link_order=0:
		detect_stack_use_after_return=0:
		detect_leaks=0:
		abort_on_error=1:
		disable_coredump=0:
		strict_string_checks=1:
		check_initialization_order=1:
		strict_init_order=1:
		detect_odr_violation=0:
		log_path=$PWD/asan.log:
	END
	) \
		make USE_PGXS=1 IS_DEV=1 installcheck -j $(nproc) || status=$?
elif [ $CHECK_TYPE = "pg_tests" ]; then
    cd ../postgresql
    # Backport float tests patch
    wget -O float-patch.patch "https://git.postgresql.org/gitweb/?p=postgresql.git;a=patch;h=da83b1ea10c2b7937d4c9e922465321749c6785b"
    git apply float-patch.patch
    # Apply test setup SQL patches to reflect enabled OrioleDB
    git apply patches/test_setup_enable_oriole.diff
    # Initialize data directory and set OrioleDB as default AM
    initdb --locale=C -D $GITHUB_WORKSPACE/pgsql/pgdata
    sed -i "s/^#*default_table_access_method.*/default_table_access_method = 'orioledb'/" $GITHUB_WORKSPACE/pgsql/pgdata/postgresql.conf
    sed -i "s/^#*shared_preload_libraries.*/shared_preload_libraries = 'orioledb'/" $GITHUB_WORKSPACE/pgsql/pgdata/postgresql.conf
    pg_ctl -D $GITHUB_WORKSPACE/pgsql/pgdata -l pg.log start
    # Run Postgress regression tests
    make -C src/test/regress installcheck-oriole -j $(nproc) || status=$?
else
	make USE_PGXS=1 IS_DEV=1 installcheck -j $(nproc) || status=$?
fi
cd ..

exit $status
