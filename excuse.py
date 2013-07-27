# -*- coding: utf-8 -*-

# Copyright (C) 2001-2004 Anthony Towns <ajt@debian.org>
#                         Andreas Barth <aba@debian.org>
#                         Fabio Tranchitella <kobold@debian.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import re
import string


class Excuse(object):
    """Excuse class

    This class represents an update excuse, which is a detailed explanation
    of why a package can or cannot be updated in the testing distribution from
    a newer package in another distribution (like for example unstable).

    The main purpose of the excuses is to be written in an HTML file which
    will be published over HTTP. The maintainers will be able to parse it
    manually or automatically to find the explanation of why their packages
    have been updated or not.
    """

    ## @var reemail
    # Regular expression for removing the email address
    reemail = re.compile(r"<.*?>")

    def __init__(self, name):
        """Class constructor

        This method initializes the excuse with the specified name and
        the default values.
        """
        self.name = name
        self.ver = ("-", "-")
        self.maint = None
        self.urgency = None
        self.daysold = None
        self.mindays = None
        self.section = None
        self._is_valid = False
        self._dontinvalidate = False
        self.run_autopkgtest = False

        self.invalid_deps = []
        self.deps = {}
        self.sane_deps = []
        self.break_deps = []
        self.bugs = []
        self.htmlline = []

    @property
    def is_valid(self):
        return self._is_valid

    @is_valid.setter
    def is_valid(self, value):
        self._is_valid = value

    @property
    def dontinvalidate(self):
        return self._dontinvalidate

    @dontinvalidate.setter
    def dontinvalidate(self, value):
        self._dontinvalidate = value

    def set_vers(self, tver, uver):
        """Set the testing and unstable versions"""
        if tver: self.ver = (tver, self.ver[1])
        if uver: self.ver = (self.ver[0], uver)

    def set_maint(self, maint):
        """Set the package maintainer's name"""
        self.maint = self.reemail.sub("", maint)

    def set_section(self, section):
        """Set the section of the package"""
        self.section = section

    def set_urgency(self, date):
        """Set the urgency of upload of the package"""
        self.urgency = date

    def add_dep(self, name, arch):
        """Add a dependency"""
        if name not in self.deps: self.deps[name]=[]
        self.deps[name].append(arch)

    def add_sane_dep(self, name):
        """Add a sane dependency"""
        if name not in self.sane_deps: self.sane_deps.append(name)

    def add_break_dep(self, name, arch):
        """Add a break dependency"""
        if (name, arch) not in self.break_deps:
            self.break_deps.append( (name, arch) )

    def invalidate_dep(self, name):
        """Invalidate dependency"""
        if name not in self.invalid_deps: self.invalid_deps.append(name)

    def setdaysold(self, daysold, mindays):
        """Set the number of days from the upload and the minimum number of days for the update"""
        self.daysold = daysold
        self.mindays = mindays

    def addhtml(self, note):
        """Add a note in HTML"""
        self.htmlline.append(note)

    def html(self):
        """Render the excuse in HTML"""
        lp_pkg = "http://packages.tanglu.org/%s" % self.name
        if self.ver[0] == "-":
            lp_old = self.ver[0]
        else:
            lp_old = "<a href=\"%s/%s\">%s</a>" % (
                lp_pkg, self.ver[0], self.ver[0])
        if self.ver[1] == "-":
            lp_new = self.ver[1]
        else:
            lp_new = "<a href=\"%s/%s\">%s</a>" % (
                lp_pkg, self.ver[1], self.ver[1])
        res = (
            "<a id=\"%s\" name=\"%s\" href=\"%s\">%s</a> (%s to %s)\n<ul>\n" %
            (self.name, self.name, lp_pkg, self.name, lp_old, lp_new))
        if self.maint:
            res = res + "<li>Maintainer: %s\n" % (self.maint)
        if self.section and string.find(self.section, "/") > -1:
            res = res + "<li>Section: %s\n" % (self.section)
        if self.daysold != None:
            if self.daysold < self.mindays:
                res = res + ("<li>Too young, only %d of %d days old\n" %
                (self.daysold, self.mindays))
            else:
                res = res + ("<li>%d days old (needed %d days)\n" %
                (self.daysold, self.mindays))
        for x in self.htmlline:
            res = res + "<li>" + x + "\n"
        lastdep = ""
        for x in sorted(self.deps, lambda x,y: cmp(x.split('/')[0], y.split('/')[0])):
            dep = x.split('/')[0]
            if dep == lastdep: continue
            lastdep = dep
            if x in self.invalid_deps:
                res = res + "<li>Depends: %s <a href=\"#%s\">%s</a> (not considered)\n" % (self.name, dep, dep)
            else:
                res = res + "<li>Depends: %s <a href=\"#%s\">%s</a>\n" % (self.name, dep, dep)
        for (n,a) in self.break_deps:
            if n not in self.deps:
                res += "<li>Ignoring %s depends: <a href=\"#%s\">%s</a>\n" % (a, n, n)
        if self.is_valid:
            res += "<li>Valid candidate\n"
        res = res + "</ul>\n"
        return res
