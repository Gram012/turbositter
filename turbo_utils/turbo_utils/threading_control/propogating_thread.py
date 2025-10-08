from threading import Thread
'''
Source: https://stackoverflow.com/questions/2829329/catch-a-threads-exception-in-the-caller-thread
''' 

class PropagatingThread(Thread):
    """ Wrapper for the thread class. If an exception is raised in this thread, 
        it will also be raised in the caller thread when the PropagatingThread 
        is join()ed.
        Otherwise, the thread would die, and the caller would never find out.
    """

    def run(self):
        self.exc = None
        try:
            self.ret = self._target(*self._args, **self._kwargs)
        except BaseException as e:
            self.exc = e

    def join(self, timeout=None):
        super(PropagatingThread, self).join(timeout)
        if self.exc:
            raise self.exc
        return self.ret


# Demo 
if __name__ == "__main__":
    def f(*args, **kwargs):
        print(args)
        print(kwargs)
        raise Exception('I suck at this')

    t = PropagatingThread(target=f, args=(5,), kwargs={'hello':'world'})
    t.start()
    t.join()
    while True:
        pass