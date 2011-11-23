from distutils.core import setup
from DistUtilsExtra.command import *

setup(name='cert-handler',
 version='0.1',
    author='David Amian',
    author_email='damian@emergya.com',
    data_files=[('bin',['scripts/cert-handler']),
                ('share/applications',['data/cert-handler.desktop'])],
    cmdclass = { "build" : build_extra.build_extra,
        "build_i18n" :  build_i18n.build_i18n,
        "clean": clean_i18n.clean_i18n, 
        }
    )
