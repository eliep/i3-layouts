#!/usr/bin/env bash

I3=`which i3`
test -x "$I3" || echo "i3 executable not found."

$I3 -c ./test/config/i3/config > /dev/null 2>&1 &
I3PID=$!
sleep 10

PYTHONPATH=. python ./i3l/connect.py &
I3LAYOUTPID=$!
sleep 0.5

PYTHONPATH=. pytest
TEST_EXIT_CODE=$?

kill "$I3LAYOUTPID"
kill "$I3PID"

exit $TEST_EXIT_CODE
