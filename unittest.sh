#!/usr/bin/env bash

I3=`which i3`
XEPHYR=`which Xephyr`
XVFB=`which Xvfb`

test -x "$I3" || echo "i3 executable not found."
test -x "$XEPHYR" || echo "Xephyr executable not found."
test -x "$XVFB" || echo "Xvfb executable not found."

PORT=2
if [ -n "$1" ] && [ "$1" = "xephir" ]
then
  $XEPHYR :$PORT -screen 1280x800 -nolisten tcp -name i3layouts > /dev/null 2>&1 &
else
  $XVFB :$PORT -screen 0 1280x800x24 -nolisten tcp > /dev/null 2>&1 &
fi
XPID=$!
sleep 0.5

DISPLAY=:$PORT $I3 -c ./test/config/i3/config > /dev/null 2>&1 &
I3PID=$!
sleep 2

PYTHONPATH=. DISPLAY=:$PORT python ./i3l/connect.py --debug &
I3LAYOUTPID=$!
sleep 0.5

PYTHONPATH=. DISPLAY=:$PORT python -W ignore -m unittest -f test.test_layouts
TEST_EXIT_CODE=$?

kill "$I3LAYOUTPID"
kill "$I3PID"
kill "$XPID"

exit $TEST_EXIT_CODE
