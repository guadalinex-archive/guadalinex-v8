/* fdsend - SCM_RIGHTS file descriptor passing for Python.
 *
 * $Id: fdsend.c,v 1.1.1.1 2004/11/04 06:15:03 mjp Exp $
 *
 * Copyright (C) 2004 Michael J. Pomraning <mjp{AT}pilcrow.madison.wi.us>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 * 
 * Portions of this file -- preliminary defines and socketpair() routine --
 * are derived from scgi version 1.2, which is is Copyright (c) 2004
 * Corporation for National Research Initiatives; All Rights Reserved.
 */

#include "Python.h"

#ifndef __OpenBSD__
#ifndef _XOPEN_SOURCE
#define _XOPEN_SOURCE 500
#endif
#ifndef _XOPEN_SOURCE_EXTENDED
#define _XOPEN_SOURCE_EXTENDED 1 /* Solaris <= 2.7 needs this too */
#endif
#endif /* __OpenBSD__ */

#include <sys/types.h>
#include <sys/socket.h>
#include <sys/uio.h>
#include <stddef.h>

static PyObject *socketmodule_error = NULL;

/* obj2fd
 *
 * A PyArg_Parse... format converter.
 */
static int
obj2fd(PyObject *o, void *p) {
	int fd = -1;

	if (o == Py_None)
		goto okay;

	if ((fd = PyObject_AsFileDescriptor(o)) == -1)
		return 0;
okay:
	*(int *)p = fd;

	return 1;
}

/* pack_control
 *
 * Cram a sequence of open files (or file descriptors) into the ancillary
 * data of a msghdr.  Note that the msg_control member is dynamically
 * allocated by this function, and may be freed by a call to
 * free_packed_control().
 */
static int
pack_control(PyObject *seq, struct msghdr *msg) {
	PyObject *fast_seq = NULL;
	int i, sz;
	int *fd_ptr = NULL;
	struct cmsghdr *cmsg;
	int ok = 0;

	fast_seq = PySequence_Fast(seq, "files argument must be a sequence");
	if (NULL == fast_seq) return 0;

	sz = PySequence_Fast_GET_SIZE(fast_seq);
	if (0 == sz) {
		msg->msg_controllen = 0;
		msg->msg_control = NULL;
		return 1;
	}
	msg->msg_controllen = CMSG_SPACE(sizeof(int) * sz);
	msg->msg_control = PyMem_Malloc(msg->msg_controllen);
	if (NULL == msg->msg_control) return 0;

	cmsg = CMSG_FIRSTHDR(msg);
	cmsg->cmsg_len = CMSG_LEN(sizeof(int) * sz);
	cmsg->cmsg_level = SOL_SOCKET;
	cmsg->cmsg_type = SCM_RIGHTS;
	fd_ptr = (int *)CMSG_DATA(cmsg);
	for (i = 0; i < sz; i++) {
		PyObject *f;
		int fd;

		f = PySequence_Fast_GET_ITEM(fast_seq, i);
		if (f == NULL) goto error;
		if ((fd = PyObject_AsFileDescriptor(f)) == -1) goto error;
		*fd_ptr = fd;
		fd_ptr++;
	}
	ok = 1;

out:
	Py_DECREF(fast_seq);
	return ok;

error:
	ok = 0;
	if (msg->msg_control) PyMem_Free(msg->msg_control);
	goto out;
}

static void
free_packed_control(struct msghdr *msg)
{
	if (NULL == msg) return;
	if (msg->msg_control) PyMem_Free(msg->msg_control);
	return;
}

/* unpack_control
 *
 * Unpack the ancillary data, assuming SCM_RIGHTS (file descriptor passing).
 *
 * Be prepared for:
 *   - more than one cmsghdr
 *   - more than one fd per cmsghdr
 */
static PyObject *
unpack_control(struct msghdr *msg) {
	struct cmsghdr *cmsg;
	int i = 0;
	PyObject *tup = NULL;

	for (cmsg = CMSG_FIRSTHDR(msg);
	     cmsg != NULL;
	     cmsg = CMSG_NXTHDR(msg,cmsg)) {
		if (cmsg->cmsg_level != SOL_SOCKET
		    || cmsg->cmsg_type != SCM_RIGHTS) {
			PyErr_SetString(PyExc_RuntimeError,
					"Unexpected cmsg level or type found");
			goto error;
		}
		i += (cmsg->cmsg_len - sizeof(struct cmsghdr))/sizeof(int);
	}

	tup = PyTuple_New(i);
	if (NULL == tup) goto error;

	i = 0;
	for (cmsg = CMSG_FIRSTHDR(msg);
	     cmsg != NULL; 
	     cmsg = CMSG_NXTHDR(msg,cmsg)) {
		int j;
		int *pfd = (int *)CMSG_DATA(cmsg);
		int upper_bound;
		upper_bound = cmsg->cmsg_len
			      - sizeof(struct cmsghdr) 
			      - sizeof(int);
		for (j = 0; j <= upper_bound; j += sizeof(int)) {
			PyTuple_SET_ITEM(tup, i, PyLong_FromLong((long)pfd[i]));
			i++;
		}
	}
	return tup;
error:
	if (tup) { Py_DECREF(tup); }

	return NULL;
}

static PyObject *
fdsend_sendfds(PyObject *dummy, PyObject *args, PyObject *kw)
{
	struct msghdr mh;
	struct iovec iov;
	int fd, r, flags = 0;
	PyObject *fds = Py_None;

	static char *keywords[] = {"fd", "msg", "flags", "fds", 0};
	if (!PyArg_ParseTupleAndKeywords(args, kw, "O&s#|iO:sendfds",
					 keywords,
					 obj2fd, &fd,
					 &iov.iov_base, &iov.iov_len,
					 &flags, &fds))
		return NULL;

	memset(&mh, '\0', sizeof(mh));
	mh.msg_iov = &iov;
	mh.msg_iovlen = 1;

	if (fds != Py_None) {
		if (! pack_control(fds, &mh)) return NULL;
	}
	Py_BEGIN_ALLOW_THREADS
	r = sendmsg(fd, &mh, flags);
	Py_END_ALLOW_THREADS
	free_packed_control(&mh);

	if (r < 0)
		return PyErr_SetFromErrno(socketmodule_error);

	return PyInt_FromLong((long) r);
}

static PyObject *
fdsend_recvfds(PyObject *dummy, PyObject *args, PyObject *kw)
{
	struct msghdr mh;
	struct iovec iov;
	struct cmsghdr *cmsg;
	PyObject *buf;
	int numfds = 32;
	int fd, r, flags = 0;
	PyObject *ret = NULL;

	static char *keywords[] = {"fd", "len", "flags", "numfds", 0};
	if (!PyArg_ParseTupleAndKeywords(args, kw, "O&i|ii:recvfds", keywords,
					obj2fd, &fd, &iov.iov_len, &flags,
					&numfds))
		return NULL;

	memset(&mh, '\0', sizeof(mh));
	
	if (numfds > 0) {
		mh.msg_controllen = CMSG_SPACE(sizeof(int) * numfds);
		mh.msg_control = PyMem_Malloc(mh.msg_controllen);
		if (NULL == mh.msg_control) return NULL;
	}

	buf = PyString_FromStringAndSize((char *) 0, iov.iov_len);
	if (NULL == buf) goto error;
	iov.iov_base = (void *)PyString_AS_STRING(buf);
	/* uncomment the following for clearer strace(1)ing */
	/* memset(iov.iov_base, '\0', iov.iov_len); */

	mh.msg_iov = &iov;
	mh.msg_iovlen = 1;

	Py_BEGIN_ALLOW_THREADS
	r = recvmsg(fd, &mh, flags);
	Py_END_ALLOW_THREADS

	if (r < 0) {
		PyErr_SetFromErrno(socketmodule_error);
		goto error;
	}
	
	if (r != iov.iov_len)
		_PyString_Resize(&buf, r);
	cmsg = CMSG_FIRSTHDR(&mh);
	if (NULL == cmsg
	    || cmsg->cmsg_level != SOL_SOCKET
	    || cmsg->cmsg_type != SCM_RIGHTS)
		return Py_BuildValue("(N())", buf);

	ret = Py_BuildValue("(OO)", buf, unpack_control(&mh));

out:
	if (mh.msg_control) PyMem_Free(mh.msg_control);
	return ret;

error:
	if (buf) { Py_DECREF(buf); }
	goto out;
}

static char fdsend_sendfds__doc__[] =
"sendfds(fd, msg, flags=0, fds=None) -> bytes_sent\n"
"\n"
"Send msg across the socket represented by fd, optionally accompanied by a\n"
"sequence (tuple or list) of open file handles.  For example:\n"
"\n"
"  >>> devnull = file(\"/dev/null\")\n"
"  >>> sendfds(the_socket, \"null device\", (devnull,))\n"
"\n"
"The socket fd and members of the fds sequence may be any representation\n"
"described in the module docstring.\n"
"\n"
"Note that most underlying implementations require at least a one byte msg\n"
"to transmit open files.";

static char fdsend_recvfds__doc__[] =
"recvfds(fd, len, flags=0, numfds=64) -> (message, fd_tuple)\n"
"\n"
"Receive a message of up to length len and up to numfds new files from socket\n"
"object fd.\n"
"\n"
"Though the socket object may be given as any of the representations listed\n"
"in the module docstring, new files returned in fd_tuple are always integral\n"
"file descriptors.  See os.fdopen for a means of transforming them into\n"
"Python file objects.\n"
"\n"
"There is presently no way to detect msg_flags values (e.g., MSG_CTRUNC).";

static char socketpair__doc__[] =
"socketpair(family, type, proto=0) -> (fd, fd)\n"
"\n"
"Provided as a convenience for Python versions lacking a socket.socketpair\n"
"implementation.";

static PyObject *
fdsend_socketpair(PyObject *self, PyObject *args)
{
	int family, type, proto=0;
	int fd[2];

	if (!PyArg_ParseTuple(args, "ii|i:socketpair", &family, &type, &proto))
		return NULL;

	if (socketpair(family, type, proto, fd) < 0) {
		PyErr_SetFromErrno(PyExc_IOError);
		return NULL;
	}

	return Py_BuildValue("(ii)", (long) fd[0], (long) fd[1]);
}


/* List of functions */

static PyMethodDef fdsend_methods[] = {
	{"sendfds", (PyCFunction)fdsend_sendfds,
		METH_VARARGS|METH_KEYWORDS, fdsend_sendfds__doc__},
	{"recvfds", (PyCFunction)fdsend_recvfds,
		METH_VARARGS|METH_KEYWORDS, fdsend_recvfds__doc__},
	{"socketpair",	fdsend_socketpair, METH_VARARGS, socketpair__doc__},
	{NULL,		NULL}		/* sentinel */
};

static char module__doc__[] =
"fdsend allows the passing of open files between unrelated processes via\n"
"local sockets (using SCM_RIGHTS), a process known as file descriptor\n"
"passing.  The following functions are available:\n"
"\n"
"  sendfds()\n"
"  recvfds()\n"
"  socketpair()\n"
"\n"
"Unlike some other simplifications of the sendmsg()/recvmsg() interface,\n"
"fdsend allows multiple files to be transferred in a single operation, and\n"
"permits ordinary socket messages to accompany the files.  Additionally,\n"
"fdsend understands bona fide Python sockets and files, as well as objects\n"
"implementing fileno() methods and integers representing file descriptors.\n"
"\n"
"Errors are raised via the socket.error exception object.";

DL_EXPORT(void)
initfdsend(void)
{
	PyObject *m, *sm;

	/* Create the module and add the functions and documentation */
	m = Py_InitModule3("fdsend", fdsend_methods, module__doc__);
	if ((sm = PyImport_ImportModule("socket")) != NULL) {
		socketmodule_error = PyObject_GetAttrString(sm, "error");
	}
}
