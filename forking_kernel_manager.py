import uuid
import os
import signal
import resource
try:
    from IPython.kernel.zmq.kernelapp import IPKernelApp
except ImportError:
    # old IPython
    from IPython.zmq.ipkernel import IPKernelApp
from IPython.config.loader import Config
from multiprocessing import Process, Pipe
import logging

def makedirs(path):
    import errno
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST:
            pass
        else: raise
    
class KernelError(Exception):
    """
    An error relating to starting up kernels
    """
    pass

class ForkingKernelManager(object):
    """ A class for managing multiple kernels and forking on the untrusted side. """
    def __init__(self, filename, ip, update_function=None, tmp_dir = None):
        self.kernels = {}
        self.ip = ip
        self.filename = filename
        self.update_function = update_function
        self.dir = tmp_dir
        makedirs(self.dir)

    def fork_kernel(self, config, pipe, resource_limits, logfile):
        """ A function to be set as the target for the new kernel processes forked in ForkingKernelManager.start_kernel. This method forks and initializes a new kernel, uses the update_function to update the kernel's namespace, sets resource limits for the kernel, and sends kernel connection information through the Pipe object.

        :arg IPython.config.loader config: kernel configuration
        :arg multiprocessing.Pipe pipe: a multiprocessing connection object which will send kernel ip, session, and port information to the other side
        :arg dict resource_limits: a dict with keys resource.RLIMIT_* (see config_default documentation for explanation of valid options) and values of the limit for the given resource to be set in the kernel process
        """
        os.setpgrp()
        logging.basicConfig(filename=self.filename,format=str(uuid.uuid4()).split('-')[0]+': %(asctime)s %(message)s',level=logging.DEBUG)
        logging.debug("kernel forked; now starting and configuring")
        try:
            ka = IPKernelApp.instance(config=config, ip=config["ip"])
            from namespace import InstrumentedNamespace
            ka.user_ns = InstrumentedNamespace()
            ka.initialize([])
        except:
            logging.exception("Error initializing IPython kernel")
        try:
            if self.update_function is not None:
                self.update_function(ka)
        except:
            logging.exception("Error configuring up kernel")
        logging.debug("finished updating")
        for r, limit in resource_limits.iteritems():
            resource.setrlimit(getattr(resource, r), (limit, limit))
        pipe.send({"ip": ka.ip, "key": ka.session.key, "shell_port": ka.shell_port,
                "stdin_port": ka.stdin_port, "hb_port": ka.hb_port, "iopub_port": ka.iopub_port})
        pipe.close()
        ka.start()

    def start_kernel(self, kernel_id=None, config=None, resource_limits=None, logfile = None):
        """ A function for starting new kernels by forking.

        :arg str kernel_id: the id of the kernel to be started. if no id is passed, a uuid will be generated
        :arg Ipython.config.loader config: kernel configuration
        :arg dict resource_limits: a dict with keys resource.RLIMIT_* (see config_default documentation for explanation of valid options) and values of the limit for the given resource to be set in the kernel process
        :returns: kernel id and connection information which includes the kernel's ip, session key, and shell, heartbeat, stdin, and iopub port numbers
        :rtype: dict
        """
        if kernel_id is None:
            kernel_id = str(uuid.uuid4())
        if config is None:
            config = Config({"ip": self.ip})
        if resource_limits is None:
            resource_limits = {}
        config.HistoryManager.enabled = False

        dir = os.path.join(self.dir, kernel_id)
        try:
            os.mkdir(dir)
        except OSError as e:
            # TODO: take care of race conditions and other problems with us
            # using an 'unclean' directory
            pass
        currdir = os.getcwd()
        os.chdir(dir)

        p, q = Pipe()
        proc = Process(target=self.fork_kernel, args=(config, q, resource_limits, logfile))
        proc.start()
        os.chdir(currdir)
        # todo: yield back to the message processing while we wait
        if p.poll(2):
            connection = p.recv()
            p.close()
            self.kernels[kernel_id] = (proc, connection)
            return {"kernel_id": kernel_id, "connection": connection}
        else:
            p.close()
            self.kill_process(proc)
            raise KernelError("Could not start kernel")

    def kill_process(self, proc):
        try:
            success = True
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            # todo: yield back to message processing loop while we join
            proc.join()
        except Exception as e:
            # On Unix, we may get an ESRCH error if the process has already
            # terminated. Ignore it.
            from errno import ESRCH
            if e.errno !=  ESRCH:
                success = False
        return success

    def kill_kernel(self, kernel_id):
        """ A function for ending running kernel processes.

        :arg str kernel_id: the id of the kernel to be killed
        :returns: whether or not the kernel process was successfully killed
        :rtype: bool
        """
        success = False

        if kernel_id in self.kernels:
            proc = self.kernels[kernel_id][0]
            success = self.kill_process(proc)
            if success:
                del self.kernels[kernel_id]
        return success

    def interrupt_kernel(self, kernel_id):
        """ A function for interrupting running kernel processes.

        :arg str kernel_id: the id of the kernel to be interrupted
        :returns: whether or not the kernel process was successfully interrupted
        :rtype: bool
        """
        success = False

        if kernel_id in self.kernels:
            try:
                os.kill(self.kernels[kernel_id][0].pid, signal.SIGINT)
                success = True
            except:
                pass

        return success

    def restart_kernel(self, kernel_id):
        """ A function for restarting running kernel processes.

        :arg str kernel_id: the id of the kernel to be restarted
        :returns: kernel id and connection information which includes the kernel's ip, session key, and shell, heartbeat, stdin, and iopub port numbers for the restarted kernel
        :rtype: dict
        """
        ports = self.kernels[kernel_id][1]
        self.kill_kernel(kernel_id)
        return self.start_kernel(kernel_id, Config({"IPKernelApp": ports, "ip": self.ip}))

if __name__ == "__main__":
    def f(a,b,c,d):
        return 1
    a = ForkingKernelManager("/dev/null", f)
    x = a.start_kernel()
    y = a.start_kernel()
    import time
    time.sleep(5)
    a.kill_kernel(x["kernel_id"])
    a.kill_kernel(y["kernel_id"])
