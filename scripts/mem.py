"""Report peak memory of this process (Windows + Linux).

Kept in one place because the OCR verification scripts need it: the Render free
tier has 512 MB, so "peak memory while OCR ran" is a number worth asserting.
"""
import ctypes
import sys


def rss_mb():
    """Peak working-set size of the current process, in MB."""
    if sys.platform.startswith('win'):
        import ctypes.wintypes as w

        class PMC(ctypes.Structure):
            _fields_ = [
                ('cb', w.DWORD), ('PageFaultCount', w.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t),
            ]

        counters = PMC()
        counters.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(PMC), w.DWORD]
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(counters), counters.cb)
        return counters.PeakWorkingSetSize / (1024 * 1024) if ok else -1

    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
