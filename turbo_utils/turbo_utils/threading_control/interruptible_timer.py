from turbo_utils.threading_control.thread_exceptions import *
import threading

class InterruptibleTimer:
    """! A timer which can be interrupted from another thread of execution
    """
    def __init__(self):
        """! Constructor for an InterruptibleTimer
        """
        
        ## @var condition
        #   The condition variable for implementing the interruptible timer
        self.condition = threading.Condition()

        ## @var exception
        #   The exception that can be raised by the timer when interrupted
        self.exception = None
    
    def sleep(self, time: float):
        """! Have the timer wait for a time
        @param time The amount of time to wait (seconds)
        """
        with self.condition:
            interrupted = self.condition.wait(time)

            if (interrupted):
                if self.exception:
                    raise self.exception
                else:
                    raise TimerInterrupted("Timer has been interrupted while waiting")
    
    def interrupt(self, exception=None):
        """! Interrupt the waiting of the timer
        @param exception    The exception to raise
        """
        with self.condition:
            self.exception = exception
            self.condition.notify_all()

_shared_timer = InterruptibleTimer()

def sleep(time):
    global _shared_timer
    _shared_timer.sleep(time)

def interrupt(exception=None):
    _shared_timer.interrupt(exception)

def test_function(timer):
    print("Sleeping")
    timer.sleep(5)
    print("Awakened")

if __name__ == "__main__":
    timer = InterruptibleTimer()

    thread = threading.Thread(target=test_function, args=(timer,))

    print("Starting the Test")
    thread.start()

    thread.join()
    print("Done")