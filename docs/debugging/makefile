all: ExampleBacktrace2.class example-backtrace-3 example-leak \
  ExampleBacktrace2.class
	
ExampleBacktrace2.class: ExampleBacktrace2.java
	javac $<

example-backtrace-3: example-backtrace-3.cpp
	${CXX} -g $< -o ./example-backtrace-3

example-leak: example-leak.c
	${CC} -Wall -g $< -o $@

clean:
	-rm example-leak example-backtrace-3
