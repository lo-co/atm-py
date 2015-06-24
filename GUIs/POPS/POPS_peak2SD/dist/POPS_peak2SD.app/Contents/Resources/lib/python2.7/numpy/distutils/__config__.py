# This file is generated by /opt/local/var/macports/build/_opt_mports_dports_python_py-numpy/py27-numpy/work/numpy-1.9.2/setup.py
# It contains system_info results at the time of building this package.
__all__ = ["get_info", "show"]

atlas_3_10_blas_info = {}
atlas_3_10_blas_threads_info = {}
atlas_threads_info = {}
blas_opt_info = {'extra_link_args': ['-Wl,-framework', '-Wl,Accelerate'], 'define_macros': [('NO_ATLAS_INFO', 3)],
                 'extra_compile_args': ['-msse3', '-DAPPLE_ACCELERATE_SGEMV_PATCH',
                                        '-I/System/Library/Frameworks/vecLib.framework/Headers']}
atlas_blas_threads_info = {}
openblas_info = {}
lapack_opt_info = {'extra_link_args': ['-Wl,-framework', '-Wl,Accelerate'], 'define_macros': [('NO_ATLAS_INFO', 3)],
                   'extra_compile_args': ['-msse3', '-DAPPLE_ACCELERATE_SGEMV_PATCH']}
openblas_lapack_info = {}
atlas_3_10_threads_info = {}
atlas_info = {}
atlas_3_10_info = {}
lapack_mkl_info = {}
blas_mkl_info = {}
atlas_blas_info = {}
mkl_info = {}


def get_info(name):
    g = globals()
    return g.get(name, g.get(name + "_info", {}))


def show():
    for name, info_dict in globals().items():
        if name[0] == "_" or type(info_dict) is not type({}): continue
        print(name + ":")
        if not info_dict:
            print("  NOT AVAILABLE")
        for k, v in info_dict.items():
            v = str(v)
            if k == "sources" and len(v) > 200:
                v = v[:60] + " ...\n... " + v[-60:]
            print("    %s = %s" % (k, v))
