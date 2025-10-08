from turbo_utils.threading_control.thread_with_exception import ThreadWithException, raise_exception_in_main_thread
import turbo_utils.threading_control.interruptible_timer as interruptible_timer
from turbo_utils.threading_control.thread_exceptions import *

def _run_interruptible_thread(function):
    """! A wrapper to catch interruptions
    """
    def wrapper_interruptible_thread(*args, **kwargs):
        try:
            function(*args, **kwargs)
        except ThreadInterrupted:
            pass
    return wrapper_interruptible_thread

class InterruptibleThread(ThreadWithException):
    """ A Thread which can be interrupted asynchronously from other threads via exceptions
    """
    def __init__(self, target=None, args=(), daemon=False):
        """! Construct an instance of Interruptible thread
        @param target   The function target
        @param args     The argument targets
        """
        super().__init__(target=target, args=args, daemon=daemon)
        ## A list of interruptible primitives that should be interrupted when this thread is interrupted
        self.interrupt_handlers = []
        
    def interrupt(self, exception=None):
        """ Interrupt the running thread by throwing an exception
        @param exception    The exception to throw
        """
        # interrupt all timers using the shared timer
        interruptible_timer.interrupt(exception)
        
        # call all other interrupt handlers
        for interrupt_handler in self.interrupt_handlers:
            interrupt_handler.interrupt(exception)

        # raise an exception in the thread
        if exception:
            self.raise_exception(exception)
        else:
            self.raise_exception(ThreadInterrupted)
    
    def add_interrupt_handler(self, handler):
        """ Add a thread or other interruptible object which should be interrupted when the thread is interrupted
        @param handler  Any object which is interruptible
        """
        self.interrupt_handlers.append(handler)


def interrupt_main_thread():
    raise_exception_in_main_thread(ThreadInterrupted)
