''' Copyright (c) 2013 Potential Ventures Ltd
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of Potential Ventures Ltd nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL POTENTIAL VENTURES LTD BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. '''

"""
All things relating to regression capabilities
"""

import time
import logging


import simulator

import cocotb
from cocotb.triggers import NullTrigger

import cocotb.ANSI as ANSI

from cocotb.result import TestError, TestFailure, TestSuccess

def _my_import(name):
    mod = __import__(name)
    components = name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


class RegressionManager(object):
    """Encapsulates all regression capability into a single place"""

    def __init__(self, dut, modules, test=None):
        """
        Args:
            modules (list): A list of python module names to run

        Kwargs
        """
        self._queue = []
        self._dut = dut
        self._modules = modules
        self._function = test
        self._running_test = None
        self.log = logging.getLogger("cocotb.regression")

    def initialise(self):

        self.ntests = 0
        self.count = 1

        xml = ""

        # Auto discovery
        for module_name in self._modules:
            module = _my_import(module_name)

            if self._function:

                # Single function specified, don't auto discover
                if not hasattr(module, self._function):
                    raise AttributeError("Test %s doesn't exist in %s" %
                        (self._function, module_name))

                self._queue.append(getattr(module, self._function)(self._dut))
                self.ntests = 1
                break

            for thing in vars(module).values():
                if hasattr(thing, "im_test"):
                    try:
                        self._queue.append(thing(self._dut))
                    except TestError:
                        self.log.warning("Skipping test %s" % thing.name)
                        xml += xunit_output(thing.name, module_name, 0.0, skipped=True)
                        continue
                    self.ntests += 1
                    self.log.info("Found test %s.%s" %
                        (self._queue[-1].module,
                        self._queue[-1].funcname))

        self.start_xml(self.ntests)
        self._fout.write(xml + '\n')

    def start_xml(self, ntests):
        """Write the XML header into results.txt"""
        self._fout = open("results.xml", 'w')
        self._fout.write("""<?xml version="1.0" encoding="UTF-8"?>\n""")
        self._fout.write("""<testsuite name="all" tests="%d" package="all">\n""" % ntests)

    def tear_down(self):
        """It's the end of the world as we know it"""
        self._fout.write("</testsuite>")
        self._fout.close()
        self.log.info("Shutting down...")
        simulator.stop_simulator()

    def next_test(self):
        """Get the next test to run"""
        if not self._queue: return None
        return self._queue.pop(0)


    def handle_result(self, result):
        """Handle a test result

        Dumps result to XML and schedules the next test (if any)

        Args: result (TestComplete exception)
        """

        if isinstance(result, TestFailure) and not \
            self._running_test.expect_fail:
            self._fout.write(xunit_output(self._running_test.funcname,
                            self._running_test.module,
                            time.time() - self._running_test.start_time,
                            failure="\n".join(self._running_test.error_messages)))
        else:
            self._fout.write(xunit_output(self._running_test.funcname,
                            self._running_test.module,
                            time.time() - self._running_test.start_time))

	self.execute()

    def execute(self):
        self._running_test = cocotb.regression.next_test()
        if self._running_test:
            # Want this to stand out a little bit
            self.log.info("%sRunning test %d/%d:%s %s" % (
               ANSI.BLUE_BG +ANSI.BLACK_FG,
                    self.count, self.ntests,
               ANSI.DEFAULT_FG + ANSI.DEFAULT_BG,
                    self._running_test))
            if self.count is 1:
                test = cocotb.scheduler.add(self._running_test)
            else:
                test = cocotb.scheduler.new_test(self._running_test)
            self.count+=1
        else:
            self.tear_down()   


def xunit_output(name, classname, time, skipped=False, failure="", error=""):
    """
    Format at xunit test output in XML

    Args:
        name (str):     the name of the test

        classname (str): the name of the class

        time (float): duration of the test in seconds

    Kwargs:
        skipped (bool): this test was skipped

        failure (str): failure message to report

        error (str): error message to report

    Returns an XML string

    """
    xml = """  <testcase classname="%s" name="%s" time="%f" """ % \
            (classname, name, time)

    if not skipped and not failure and not error:
        return xml + " />\n"
    else:
        xml += ">\n"

    if skipped:
        xml += "    <skipped />\n"

    if failure:
        xml += "    <failure message=\"test failure\">%s\n    </failure>\n" % \
            failure

    if error:
        xml += "    <error message=\"test failure\">%s\n    </error>\n" % \
            error

    return xml + "  </testcase>\n"