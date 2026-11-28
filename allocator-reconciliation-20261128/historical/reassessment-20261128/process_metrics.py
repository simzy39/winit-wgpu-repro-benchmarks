"""Read child-process CPU accounting after exit while its Windows handle remains open."""
import subprocess,time,ctypes
from ctypes import wintypes
class FileTime(ctypes.Structure):
    _fields_=[("low",wintypes.DWORD),("high",wintypes.DWORD)]
def process_cpu(handle):
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    query=kernel.GetProcessTimes
    query.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(FileTime)]*4
    query.restype=wintypes.BOOL
    creation,exit_time,kernel_time,user_time=[FileTime() for _ in range(4)]
    if not query(wintypes.HANDLE(int(handle)),ctypes.byref(creation),ctypes.byref(exit_time),ctypes.byref(kernel_time),ctypes.byref(user_time)):
        raise ctypes.WinError(ctypes.get_last_error())
    ms=lambda value:((value.high<<32)|value.low)/10000
    return {"kernel_cpu_ms":ms(kernel_time),"user_cpu_ms":ms(user_time),"total_cpu_ms":ms(kernel_time)+ms(user_time)}
def run_process(command,timeout=600):
    start=time.perf_counter()
    with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8") as child:
        timed_out=False
        try:stdout,stderr=child.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True;child.kill();stdout,stderr=child.communicate()
            stderr+="\nMeasurement timeout"
        cpu=process_cpu(child._handle)
        result=subprocess.CompletedProcess(command,child.returncode,stdout,stderr)
        result.cpu_times=cpu
        result.wall_s=time.perf_counter()-start
        result.timed_out=timed_out
        return result

