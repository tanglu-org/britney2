#!/usr/bin/python
# (C) 2014 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import mock
import os
import shutil
import sys
import tempfile
import unittest


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

import boottest
from tests import TestBase


def create_manifest(manifest_dir, lines):
    """Helper function for writing touch image manifests."""
    os.makedirs(manifest_dir)
    with open(os.path.join(manifest_dir, 'manifest'), 'w') as fd:
        fd.write('\n'.join(lines))


class FakeResponse(object):

    def __init__(self, code=404, content=''):
        self.code = code
        self.content = content

    def read(self):
        return self.content


class TestTouchManifest(unittest.TestCase):

    def setUp(self):
        super(TestTouchManifest, self).setUp()
        self.path = tempfile.mkdtemp(prefix='boottest')
        os.chdir(self.path)
        self.imagesdir = os.path.join(self.path, 'boottest/images')
        os.makedirs(self.imagesdir)
        self.addCleanup(shutil.rmtree, self.path)
        _p = mock.patch('urllib.urlopen')
        self.mocked_urlopen = _p.start()
        self.mocked_urlopen.side_effect = [FakeResponse(code=404),]
        self.addCleanup(_p.stop)
        self.fetch_retries_orig = boottest.FETCH_RETRIES
        def restore_fetch_retries():
            boottest.FETCH_RETRIES = self.fetch_retries_orig
        boottest.FETCH_RETRIES = 0
        self.addCleanup(restore_fetch_retries)

    def test_missing(self):
        # Missing manifest file silently results in empty contents.
        manifest = boottest.TouchManifest('I-dont-exist', 'vivid')
        self.assertEqual([], manifest._manifest)
        self.assertNotIn('foo', manifest)

    def test_fetch(self):
        # Missing manifest file is fetched dynamically
        self.mocked_urlopen.side_effect = [
            FakeResponse(code=200, content='foo 1.0'),
        ]
        manifest = boottest.TouchManifest('ubuntu-touch', 'vivid')
        self.assertNotEqual([], manifest._manifest)

    def test_fetch_disabled(self):
        # Manifest auto-fetching can be disabled. 
        manifest = boottest.TouchManifest('ubuntu-touch', 'vivid', fetch=False)
        self.mocked_urlopen.assert_not_called()
        self.assertEqual([], manifest._manifest)

    def test_fetch_fails(self):
        project = 'fake'
        series = 'fake'
        manifest_dir = os.path.join(self.imagesdir, project, series)
        manifest_lines = [
            'foo:armhf       1~beta1',
        ]
        create_manifest(manifest_dir, manifest_lines)
        manifest = boottest.TouchManifest(project, series)
        self.assertEqual(1, len(manifest._manifest))
        self.assertIn('foo', manifest)

    def test_fetch_exception(self):
        self.mocked_urlopen.side_effect = [IOError("connection refused")]
        manifest = boottest.TouchManifest('not-real', 'not-real')
        self.assertEqual(0, len(manifest._manifest))

    def test_simple(self):
        # Existing manifest file allows callsites to properly check presence.
        manifest_dir = os.path.join(self.imagesdir, 'ubuntu/vivid')
        manifest_lines = [
            'bar 1234',
            'foo:armhf       1~beta1',
            'boing1-1.2\t666',
            'click:com.ubuntu.shorts	0.2.346'
        ]
        create_manifest(manifest_dir, manifest_lines)

        manifest = boottest.TouchManifest('ubuntu', 'vivid')
        # We can dig deeper on the manifest package names list ...
        self.assertEqual(
            ['bar', 'boing1-1.2', 'foo'], manifest._manifest)
        # but the '<name> in manifest' API reads better.
        self.assertIn('foo', manifest)
        self.assertIn('boing1-1.2', manifest)
        self.assertNotIn('baz', manifest)
        # 'click' name is blacklisted due to the click package syntax.
        self.assertNotIn('click', manifest)


class TestBoottestEnd2End(TestBase):
    """End2End tests (calling `britney`) for the BootTest criteria."""

    def setUp(self):
        super(TestBoottestEnd2End, self).setUp()

        # Modify shared configuration file.
        with open(self.britney_conf, 'r') as fp:
            original_config = fp.read()
        # Disable autopkgtests.
        new_config = original_config.replace(
            'ADT_ENABLE        = yes', 'ADT_ENABLE        = no')
        # Disable TouchManifest auto-fetching.
        new_config = new_config.replace(
            'BOOTTEST_FETCH    = yes', 'BOOTTEST_FETCH    = no')
        with open(self.britney_conf, 'w') as fp:
            fp.write(new_config)
        self.addCleanup(self.restore_config, original_config)

        self.data.add('libc6', False, {'Architecture': 'armhf'}),

        self.data.add(
            'libgreen1',
            False,
            {'Source': 'green', 'Architecture': 'armhf',
             'Depends': 'libc6 (>= 0.9)'})
        self.data.add(
            'green',
            False,
            {'Source': 'green', 'Architecture': 'armhf',
             'Depends': 'libc6 (>= 0.9), libgreen1'})
        self.create_manifest([
            'green 1.0',
            'pyqt5:armhf 1.0',
            'signon 1.0'
        ])

    def create_manifest(self, lines):
        """Create a manifest for this britney run context."""
        path = os.path.join(
            self.data.path,
            'boottest/images/ubuntu-touch/{}'.format(self.data.series))
        create_manifest(path, lines)

    def make_boottest(self):
        """Create a stub version of boottest-britney script."""
        script_path = os.path.expanduser(
            "~/auto-package-testing/jenkins/boottest-britney")
        os.makedirs(os.path.dirname(script_path))
        with open(script_path, 'w') as f:
            f.write('''#!%(py)s
import argparse
import os
import shutil
import sys

template = """
green 1.1~beta RUNNING
pyqt5-src 1.1~beta PASS
pyqt5-src 1.1 FAIL
signon 1.1 PASS
"""

def request():
    work_path = os.path.dirname(args.output)
    os.makedirs(work_path)
    shutil.copy(args.input, os.path.join(work_path, 'test_input'))
    with open(args.output, 'w') as f:
        f.write(template)

def submit():
    pass

def collect():
    with open(args.output, 'w') as f:
        f.write(template)

p = argparse.ArgumentParser()
p.add_argument('-r')
p.add_argument('-c')
p.add_argument('-d', default=False, action='store_true')
p.add_argument('-P', default=False, action='store_true')
p.add_argument('-U', default=False, action='store_true')

sp = p.add_subparsers()

psubmit = sp.add_parser('submit')
psubmit.add_argument('input')
psubmit.set_defaults(func=submit)

prequest = sp.add_parser('request')
prequest.add_argument('-O', dest='output')
prequest.add_argument('input')
prequest.set_defaults(func=request)

pcollect = sp.add_parser('collect')
pcollect.add_argument('-O', dest='output')
pcollect.set_defaults(func=collect)

args = p.parse_args()
args.func()
                    ''' % {'py': sys.executable})
        os.chmod(script_path, 0o755)

    def do_test(self, context, expect=None, no_expect=None):
        """Process the given package context and assert britney results."""
        for (pkg, fields) in context:
            self.data.add(pkg, True, fields)
        self.make_boottest()
        (excuses, out) = self.run_britney()
        #print('-------\nexcuses: %s\n-----' % excuses)
        if expect:
            for re in expect:
                self.assertRegexpMatches(excuses, re)
        if no_expect:
            for re in no_expect:
                self.assertNotRegexpMatches(excuses, re)

    def test_runs(self):
        # `Britney` runs and considers binary packages for boottesting
        # when it is enabled in the configuration, only binaries needed
        # in the phone image are considered for boottesting.
        # 'in progress' tests blocks package promotion.
        context = [
            ('green', {'Source': 'green', 'Version': '1.1~beta',
                       'Architecture': 'armhf', 'Depends': 'libc6 (>= 0.9)'}),
            ('libgreen1', {'Source': 'green', 'Version': '1.1~beta',
                           'Architecture': 'armhf',
                           'Depends': 'libc6 (>= 0.9)'}),
        ]
        self.do_test(
            context,
            [r'\bgreen\b.*>1</a> to .*>1.1~beta<',
             '<li>Boottest result: {}'.format(
                 boottest.BootTest.EXCUSE_LABELS['RUNNING']),
             '<li>Not considered'])

        # The `boottest-britney` input (recorded for testing purposes),
        # contains a line matching the requested boottest attempt.
        # '<source> <version>\n'
        test_input_path = os.path.join(
            self.data.path, 'boottest/work/test_input')
        self.assertEqual(
            ['green 1.1~beta\n'], open(test_input_path).readlines())

    def test_pass(self):
        # `Britney` updates boottesting information in excuses when the
        # package test pass and marks the package as a valid candidate for
        # promotion.
        context = []
        context.append(
            ('signon', {'Version': '1.1', 'Architecture': 'armhf'}))
        self.do_test(
            context,
            [r'\bsignon\b.*\(- to .*>1.1<',
             '<li>Boottest result: {}'.format(
                 boottest.BootTest.EXCUSE_LABELS['PASS']),
             '<li>Valid candidate'])

    def test_fail(self):
        # `Britney` updates boottesting information in excuses when the
        # package test fails and blocks the package promotion
        # ('Not considered.')
        context = []
        context.append(
            ('pyqt5', {'Source': 'pyqt5-src', 'Version': '1.1',
                       'Architecture': 'all'}))
        self.do_test(
            context,
            [r'\bpyqt5-src\b.*\(- to .*>1.1<',
             '<li>Boottest result: {}'.format(
                 boottest.BootTest.EXCUSE_LABELS['FAIL']),
             '<li>Not considered'])

    def create_hint(self, username, content):
        """Populates a hint file for the given 'username' with 'content'."""
        hints_path = os.path.join(
            self.data.path,
            'data/{}-proposed/Hints/{}'.format(self.data.series, username))
        with open(hints_path, 'w') as fd:
            fd.write(content)

    def test_skipped_by_hints(self):
        # `Britney` allows boottests to be skipped by hinting the
        # corresponding source with 'force-skiptest'. The boottest
        # attempt will not be requested.
        context = [
            ('pyqt5', {'Source': 'pyqt5-src', 'Version': '1.1',
                       'Architecture': 'all'}),
        ]
        self.create_hint('cjwatson', 'force-skiptest pyqt5-src/1.1')
        self.do_test(
            context,
            [r'\bpyqt5-src\b.*\(- to .*>1.1<',
             '<li>boottest skipped from hints by cjwatson',
             '<li>Valid candidate'])

    def test_fail_but_forced_by_hints(self):
        # `Britney` allows boottests results to be ignored by hinting the
        # corresponding source with 'force' or 'force-badtest'. The boottest
        # attempt will still be requested and its results would be considered
        # for other non-forced sources.
        context = [
            ('pyqt5', {'Source': 'pyqt5-src', 'Version': '1.1',
                       'Architecture': 'all'}),
        ]
        self.create_hint('cjwatson', 'force pyqt5-src/1.1')
        self.do_test(
            context,
            [r'\bpyqt5-src\b.*\(- to .*>1.1<',
             '<li>Boottest result: {}'.format(
                 boottest.BootTest.EXCUSE_LABELS['FAIL']),
             '<li>Should wait for pyqt5-src 1.1 boottest, '
             'but forced by cjwatson',
             '<li>Valid candidate'])

    def test_fail_but_ignored_by_hints(self):
        # See `test_fail_but_forced_by_hints`.
        context = [
            ('green', {'Source': 'green', 'Version': '1.1~beta',
                       'Architecture': 'armhf', 'Depends': 'libc6 (>= 0.9)'}),
        ]
        self.create_hint('cjwatson', 'force-badtest green/1.1~beta')
        self.do_test(
            context,
            [r'\bgreen\b.*>1</a> to .*>1.1~beta<',
             '<li>Boottest result: {}'.format(
                 boottest.BootTest.EXCUSE_LABELS['RUNNING']),
             '<li>Should wait for green 1.1~beta boottest, but forced '
             'by cjwatson',
             '<li>Valid candidate'])

    def test_skipped_not_on_phone(self):
        # `Britney` updates boottesting information in excuses when the
        # package was skipped and marks the package as a valid candidate for
        # promotion, but no notice about 'boottest' is added to the excuse.
        context = []
        context.append(
            ('apache2', {'Source': 'apache2-src', 'Architecture': 'all',
                         'Version': '2.4.8-1ubuntu1'}))
        self.do_test(
            context,
            [r'\bapache2-src\b.*\(- to .*>2.4.8-1ubuntu1<',
             '<li>Valid candidate'],
            ['<li>Boottest result:'],
        )

    def test_skipped_architecture_not_allowed(self):
        # `Britney` does not trigger boottests for source not yet built on
        # the allowed architectures.
        self.data.add(
            'pyqt5', False, {'Source': 'pyqt5-src', 'Architecture': 'armhf'})
        context = [
            ('pyqt5', {'Source': 'pyqt5-src', 'Version': '1.1',
                       'Architecture': 'amd64'}),
        ]
        self.do_test(
            context,
            [r'\bpyqt5-src\b.*>1</a> to .*>1.1<',
             r'<li>missing build on .*>armhf</a>: pyqt5 \(from .*>1</a>\)',
             '<li>Not considered'])



if __name__ == '__main__':
    unittest.main()
