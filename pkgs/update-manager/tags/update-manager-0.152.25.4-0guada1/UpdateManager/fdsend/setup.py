#!/usr/bin/env python

# fdsend setup.py
# $Id: setup.py,v 1.1.1.1 2004/11/04 06:15:03 mjp Exp $

from distutils.core import setup
from distutils.extension import Extension

setup(name = "fdsend",
      version = "0.1",
      description = "File descriptor passing (via SCM_RIGHTS)",
      author = "Michael J. Pomraning",
      author_email = "mjp-py@pilcrow.madison.wi.us",
      url = "http://pilcrow.madison.wi.us/fdsend",
      license = "GPL",
      ext_modules = [Extension(name="fdsend", sources=['fdsend.c'])],
      )
