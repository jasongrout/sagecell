r"""
Git Interface

This module provides a python interface to Sage's git repository.

AUTHORS:

- TODO: add authors from github's history and trac's history

"""
#*****************************************************************************
#       Copyright (C) 2013 TODO
#
#  Distributed under the terms of the GNU General Public License (GPL)
#  as published by the Free Software Foundation; either version 2 of
#  the License, or (at your option) any later version.
#                  http://www.gnu.org/licenses/
#*****************************************************************************

import os

from sage.env import SAGE_DOT_GIT, SAGE_REPO_AUTHENTICATED, SAGE_SRC

from git_error import GitError

SILENT = object()
SUPER_SILENT = object()
READ_OUTPUT = object()

class GitInterface(object):
    r"""
    A wrapper around the ``git`` command line tool.

    Most methods of this class correspond to actual git commands. Some add
    functionality which is not directly available in git. However, all of the
    methods should be non-interactive. If interaction is required the method
    should live in :class:`saged.dev.sagedev.SageDev`.

    EXAMPLES::

        sage: from sage.dev.config import Config
        sage: from sage.dev.user_interface import UserInterface
        sage: from sage.dev.git_interface import GitInterface
        sage: config = Config()
        sage: GitInterface(config, UserInterface(config))
        GitInterface()

    """
    def __init__(self, config, UI):
        r"""
        Initialization.

        TESTS::

            sage: from sage.dev.config import Config
            sage: from sage.dev.user_interface import UserInterface
            sage: from sage.dev.git_interface import GitInterface
            sage: config = Config()
            sage: type(GitInterface(config, UserInterface(config)))
            <class 'sage.dev.git_interface.GitInterface'>

        """
        self._UI = UI
        self._config = config

        self._src = self._config.get('src', SAGE_SRC)
        self._dot_git = self._config.get('dot_git', SAGE_DOT_GIT)
        self._gitcmd = self._config.get('gitcmd', 'git')
        self._repository = self._config.get('repository', SAGE_REPO_AUTHENTICATED)

        if not os.path.exists(self._dot_git):
            raise ValueError("`%s` does not point to an existing directory."%self._dot_git)

    def __repr__(self):
        r"""
        Return a printable representation of this object.

        TESTS::

            sage: from sage.dev.config import Config
            sage: from sage.dev.user_interface import UserInterface
            sage: from sage.dev.git_interface import GitInterface
            sage: config = Config()
            sage: repr(GitInterface(config, UserInterface(config)))
            'GitInterface()'

        """
        return "GitInterface()"

    def get_state(self):
        r"""
        Get the current state of merge/rebase/am/etc operations.

        OUTPUT:

        A tuple of strings which consists of any of the following:
        ``'rebase'``, ``'am'``, ``'rebase-i'``, ``'rebase-m'``, ``'merge'``,
        ``'bisect'``, ``'cherry-seq'``, ``'cherry'``.

        EXAMPLES:

        Create a :class:`GitInterface` for doctesting::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface, SILENT, SUPER_SILENT
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))

        Create two conflicting branches::

            sage: os.chdir(config['git']['src'])
            sage: with open("file","w") as f: f.write("version 0")
            sage: git.add("file")
            sage: git.commit(SUPER_SILENT, "-m","initial commit")
            sage: git.checkout(SUPER_SILENT, "-b","branch1")
            sage: with open("file","w") as f: f.write("version 1")
            sage: git.commit(SUPER_SILENT, "-am","second commit")
            sage: git.checkout(SUPER_SILENT, "master")
            sage: git.checkout(SUPER_SILENT, "-b","branch2")
            sage: with open("file","w") as f: f.write("version 2")
            sage: git.commit(SUPER_SILENT, "-am","conflicting commit")

        A ``merge`` state::

            sage: git.checkout(SUPER_SILENT, "branch1")
            sage: git.merge(SUPER_SILENT, 'branch2')
            Traceback (most recent call last):
            ...
            GitError: git returned with non-zero exit code (1)
            sage: git.get_state()
            ('merge',)
            sage: git.merge(SUPER_SILENT,abort=True)
            sage: git.get_state()
            ()

        A ``rebase`` state::

            sage: git.execute_supersilent('rebase', 'branch2')
            Traceback (most recent call last):
            ...
            GitError: git returned with non-zero exit code (1)
            sage: git.get_state()
            ('rebase',)
            sage: git.rebase(SUPER_SILENT, abort=True)
            sage: git.get_state()
            ()

        A merge within an interactive rebase::

            sage: git.rebase(SUPER_SILENT, 'HEAD^', interactive=True, env={'GIT_SEQUENCE_EDITOR':'sed -i s+pick+edit+'})
            sage: git.get_state()
            ('rebase-i',)
            sage: git.merge(SUPER_SILENT, 'branch2')
            Traceback (most recent call last):
            ...
            GitError: git returned with non-zero exit code (1)
            sage: git.get_state()
            ('merge', 'rebase-i')
            sage: git.rebase(SUPER_SILENT, abort=True)
            sage: git.get_state()
            ()

        """
        # logic based on zsh's git backend for vcs_info
        opj = os.path.join
        p = lambda x: opj(self._dot_git, x)
        ret = []
        for d in map(p,("rebase-apply", "rebase", opj("..",".dotest"))):
            if os.path.isdir(d):
                if os.path.isfile(opj(d, 'rebasing')) and 'rebase' not in ret:
                    ret.append('rebase')
                if os.path.isfile(opj(d, 'applying')) and 'am' not in ret:
                    ret.append('am')
        for f in map(p, (opj('rebase-merge', 'interactive'),
                         opj('.dotest-merge', 'interactive'))):
            if os.path.isfile(f):
                ret.append('rebase-i')
                break
        else:
            for d in map(p, ('rebase-merge', '.dotest-merge')):
                if os.path.isdir(d):
                    ret.append('rebase-m')
                    break
        if os.path.isfile(p('MERGE_HEAD')):
            ret.append('merge')
        if os.path.isfile(p('BISECT_LOG')):
            ret.append('bisect')
        if os.path.isfile(p('CHERRY_PICK_HEAD')):
            if os.path.isdir(p('sequencer')):
                ret.append('cherry-seq')
            else:
                ret.append('cherry')
        # return in reverse order so reset operations are correctly ordered
        return tuple(reversed(ret))

    def reset_to_clean_state(self):
        r"""
        Get out of a merge/am/rebase/etc state.

        EXAMPLES:

        Create a :class:`GitInterface` for doctesting::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface, SILENT, SUPER_SILENT
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))

        Create two conflicting branches::

            sage: os.chdir(config['git']['src'])
            sage: with open("file","w") as f: f.write("version 0")
            sage: git.add("file")
            sage: git.commit(SUPER_SILENT, "-m","initial commit")
            sage: git.checkout(SUPER_SILENT, "-b","branch1")
            sage: with open("file","w") as f: f.write("version 1")
            sage: git.commit(SUPER_SILENT, "-am","second commit")
            sage: git.checkout(SUPER_SILENT, "master")
            sage: git.checkout(SUPER_SILENT, "-b","branch2")
            sage: with open("file","w") as f: f.write("version 2")
            sage: git.commit(SUPER_SILENT, "-am","conflicting commit")

        A merge within an interactive rebase::

            sage: git.checkout(SUPER_SILENT, "branch1")
            sage: git.rebase(SUPER_SILENT, 'HEAD^', interactive=True, env={'GIT_SEQUENCE_EDITOR':'sed -i s+pick+edit+'})
            sage: git.get_state()
            ('rebase-i',)
            sage: git.merge(SUPER_SILENT, 'branch2')
            Traceback (most recent call last):
            ...
            GitError: git returned with non-zero exit code (1)
            sage: git.get_state()
            ('merge', 'rebase-i')

        Get out of this state::

            sage: git.reset_to_clean_state()
            sage: git.get_state()
            ()

        """
        states = self.get_state()
        if not states:
            return

        state = states[0]
        if state.startswith('rebase'):
            self.execute_silent('rebase', abort=True)
        elif state == 'am':
            self.execute_silent('am', abort=True)
        elif state == 'merge':
            self.execute_silent('merge', abort=True)
        elif state == 'bisect':
            raise NotImplementedError(state)
        elif state.startswith('cherry'):
            self.execute_silent('cherry-pick', abort=True)
        else:
            raise RuntimeError("'%s' is not a valid state"%state)

        return self.reset_to_clean_state()

    def reset_to_clean_working_directory(self, remove_untracked_files=False, remove_untracked_directories=False, remove_ignored=False):
        r"""
        Reset any changes made to the working directory.

        INPUT:

        - ``remove_untracked_files`` -- a boolean (default: ``False``), whether
          to remove files which are not tracked by git

        - ``remove_untracked_directories`` -- a boolean (default: ``False``),
          whether to remove directories which are not tracked by git

        - ``remove_ignored`` -- a boolean (default: ``False``), whether to
          remove files directories which are ignored by git

        EXAMPLES:

        Create a :class:`GitInterface` for doctesting::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface, SILENT, SUPER_SILENT
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))

        Set up some files/directories::

            sage: os.chdir(config['git']['src'])
            sage: open('tracked','w').close()
            sage: git.add(SUPER_SILENT, 'tracked')
            sage: with open('.gitignore','w') as f: f.write('ignored\nignored_dir')
            sage: git.add(SUPER_SILENT, '.gitignore')
            sage: git.commit(SUPER_SILENT, '-m', 'initial commit')

            sage: os.mkdir('untracked_dir')
            sage: open('untracked_dir/untracked','w').close()
            sage: open('untracked','w').close()
            sage: open('ignored','w').close()
            sage: os.mkdir('ignored_dir')
            sage: open('ignored_dir/untracked','w').close()
            sage: with open('tracked','w') as f: f.write('version 0')
            sage: git.status()
            # On branch master
            # Changes not staged for commit:
            #   (use "git add <file>..." to update what will be committed)
            #   (use "git checkout -- <file>..." to discard changes in working directory)
            #
            #   modified:   tracked
            #
            # Untracked files:
            #   (use "git add <file>..." to include in what will be committed)
            #
            #   untracked
            #   untracked_dir/
            no changes added to commit (use "git add" and/or "git commit -a")

        Some invalid combinations of flags::

            sage: git.reset_to_clean_working_directory(remove_untracked_files = False, remove_untracked_directories = True)
            Traceback (most recent call last):
            ...
            ValueError: remove_untracked_directories only valid if remove_untracked_files is set
            sage: git.reset_to_clean_working_directory(remove_untracked_files = False, remove_ignored = True)
            Traceback (most recent call last):
            ...
            ValueError: remove_ignored only valid if remove_untracked_files is set

        Per default only the tracked modified files are reset to a clean
        state::

            sage: git.reset_to_clean_working_directory()
            sage: git.status()
            # On branch master
            # Untracked files:
            #   (use "git add <file>..." to include in what will be committed)
            #
            #   untracked
            #   untracked_dir/
            nothing added to commit but untracked files present (use "git add" to track)

        Untracked items can be removed by setting the parameters::

            sage: git.reset_to_clean_working_directory(remove_untracked_files=True)
            Removing untracked
            Not removing untracked_dir/
            sage: git.reset_to_clean_working_directory(remove_untracked_files=True, remove_untracked_directories=True)
            Removing untracked_dir/
            sage: git.reset_to_clean_working_directory(remove_untracked_files=True, remove_ignored=True)
            Removing ignored
            Not removing ignored_dir/
            sage: git.reset_to_clean_working_directory(remove_untracked_files=True, remove_untracked_directories=True, remove_ignored=True)
            Removing ignored_dir/

        """
        if remove_untracked_directories and not remove_untracked_files:
            raise ValueError("remove_untracked_directories only valid if remove_untracked_files is set")
        if remove_ignored and not remove_untracked_files:
            raise ValueError("remove_ignored only valid if remove_untracked_files is set")

        self.reset(SILENT, hard=True)

        if remove_untracked_files:
            switches = ['-f']
            if remove_untracked_directories: switches.append("-d")
            if remove_ignored: switches.append("-x")
            self.clean(*switches)

    def _run_git(self, cmd, args, kwds, **ckwds):
        r"""
        Common implementation for :meth:`execute`, :meth:`execute_silent`,
        :meth:`execute_supersilent`, and :meth:`read_output`

        INPUT:

        - ``cmd`` - git command run

        - ``args`` - extra arguments for git

        - ``kwds`` - extra keywords for git

        - ``ckwds`` - Popen like keywords but with the following changes

          - ``stdout`` - if set to ``False`` will supress stdout

          - ``stderr`` - if set to ``False`` will supress stderr

        .. WARNING::

            This method does not raise an exception if the git call returns a
            non-zero exit code.

        EXAMPLES::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))
            sage: os.chdir(config['git']['src'])

            sage: git._run_git('status', (), {})
            # On branch master
            #
            # Initial commit
            #
            nothing to commit (create/copy files and use "git add" to track)
            (0, None, None)
            sage: git._run_git('status', (), {}, stdout=False)
            (0, None, None)

        TESTS:

        Check that we refuse to touch the live source code in doctests::

            sage: dev.git.status()
            Traceback (most recent call last):
            ...
            AssertionError: attempt to work with the live repository or directory in a doctest

        """
        import sage.doctest
        import os
        assert not sage.doctest.DOCTEST_MODE or (self._dot_git != SAGE_DOT_GIT and self._repository != SAGE_REPO_AUTHENTICATED and os.path.abspath(os.getcwd()).startswith(self._src)), "attempt to work with the live repository or directory in a doctest"

        s = [self._gitcmd, "--git-dir=%s"%self._dot_git, cmd]

        env = ckwds.setdefault('env', dict(os.environ))
        env.update(kwds.pop('env', {}))

        for k, v in kwds.iteritems():
            if len(k) == 1:
                k = '-' + k
            else:
                k = '--' + k.replace('_', '-')
            if v is True:
                s.append(k)
            elif v is not False:
                s.extend((k, v))
        if args:
            s.extend(a for a in args if a is not None)

        s = [str(arg) for arg in s]

        from sage.dev.user_interface import INFO
        self._UI.show("[git] %s"%(" ".join(s)), log_level=INFO)

        if ckwds.get('dryrun', False):
            return s

        import subprocess
        devnull = open(os.devnull, 'w')
        if ckwds.get('stdout') is False:
            ckwds['stdout'] = devnull
        elif ckwds.get('stdout') is str:
            ckwds['stdout'] = subprocess.PIPE
        if ckwds.get('stderr') is False:
            ckwds['stderr'] = devnull
        elif ckwds.get('stderr') is str:
            ckwds['stderr'] = subprocess.PIPE
        process = subprocess.Popen(s, **ckwds)
        stdout, stderr = process.communicate()
        retcode = process.poll()
        return retcode, stdout, stderr

    def execute(self, cmd, *args, **kwds):
        r"""
        Run git.

        Raises an exception if git has non-zero exit code.

        INPUT:

        - ``cmd`` - git command run

        - ``args`` - extra arguments for git

        - ``kwds`` - extra keywords for git

        EXAMPLES::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))
            sage: os.chdir(config['git']['src'])

            sage: git.execute('status')
            # On branch master
            #
            # Initial commit
            #
            nothing to commit (create/copy files and use "git add" to track)
            sage: git.execute_silent('status',foo=True) # --foo is not a valid parameter
            Traceback (most recent call last):
            ...
            GitError: git returned with non-zero exit code (129)

        """
        exit_code = self._run_git(cmd, args, kwds)[0]
        if exit_code:
            raise GitError(exit_code)

    __call__ = execute

    def execute_silent(self, cmd, *args, **kwds):
        r"""
        Run git and supress its output to stdout.

        Same input as :meth:`execute`.

        Raises an error if git returns a non-zero exit code.

        EXAMPLES::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))
            sage: os.chdir(config['git']['src'])

            sage: git.execute_silent('status')
            sage: git.execute_silent('status',foo=True) # --foo is not a valid parameter
            Traceback (most recent call last):
            ...
            GitError: git returned with non-zero exit code (129)

        """
        exit_code = self._run_git(cmd, args, kwds, stdout=False)[0]
        if exit_code:
            raise GitError(exit_code)

    def execute_supersilent(self, cmd, *args, **kwds):
        r"""
        Run git and supress its output to stdout and stderr.

        Same input as :meth:`execute`.

        Raises an error if git returns a non-zero exit code.

        EXAMPLES::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))
            sage: os.chdir(config['git']['src'])

            sage: git.execute_supersilent('status')
            sage: git.execute_supersilent('status',foo=True) # --foo is not a valid parameter
            Traceback (most recent call last):
            ...
            GitError: git returned with non-zero exit code (129)

        """
        exit_code = self._run_git(cmd, args, kwds, stdout=False, stderr=False)[0]
        if exit_code:
            raise GitError(exit_code)

    def read_output(self, cmd, *args, **kwds):
        r"""
        Run git and return its output to stdout.

        Same input as :meth:`execute`.

        Raises an error if git returns a non-zero exit code.

        EXAMPLES::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))
            sage: os.chdir(config['git']['src'])

            sage: git.read_output('status')
            '# On branch master\n#\n# Initial commit\n#\nnothing to commit (create/copy files and use "git add" to track)\n'
            sage: git.read_output('status',foo=True) # --foo is not a valid parameter
            Traceback (most recent call last):
            ...
            GitError: git returned with non-zero exit code (129)

        """
        exit_code, ret, _ = self._run_git(cmd, args, kwds, stdout=str, stderr=False)
        if exit_code:
            raise GitError(exit_code)
        return ret

    def is_child_of(self, a, b):
        r"""
        Return whether ``a`` is a child of ``b``.

        EXAMPLES:

        Create a :class:`GitInterface` for doctesting::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface, SILENT, SUPER_SILENT
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))

        Create two conflicting branches::

            sage: os.chdir(config['git']['src'])
            sage: with open("file","w") as f: f.write("version 0")
            sage: git.add("file")
            sage: git.commit(SUPER_SILENT, "-m","initial commit")
            sage: git.checkout(SUPER_SILENT, "-b","branch1")
            sage: with open("file","w") as f: f.write("version 1")
            sage: git.commit(SUPER_SILENT, "-am","second commit")
            sage: git.checkout(SUPER_SILENT, "master")
            sage: git.checkout(SUPER_SILENT, "-b","branch2")
            sage: with open("file","w") as f: f.write("version 2")
            sage: git.commit(SUPER_SILENT, "-am","conflicting commit")

            sage: git.is_child_of('master', 'branch2')
            False
            sage: git.is_child_of('branch2', 'master')
            True
            sage: git.is_child_of('branch1', 'branch2')
            False
            sage: git.is_child_of('master', 'master')
            True

        """
        return self.is_ancestor_of(b, a)

    def is_ancestor_of(self, a, b):
        r"""
        Return whether ``a`` is an ancestor of ``b``.

        EXAMPLES:

        Create a :class:`GitInterface` for doctesting::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface, SILENT, SUPER_SILENT
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))

        Create two conflicting branches::

            sage: os.chdir(config['git']['src'])
            sage: with open("file","w") as f: f.write("version 0")
            sage: git.add("file")
            sage: git.commit(SUPER_SILENT, "-m","initial commit")
            sage: git.checkout(SUPER_SILENT, "-b","branch1")
            sage: with open("file","w") as f: f.write("version 1")
            sage: git.commit(SUPER_SILENT, "-am","second commit")
            sage: git.checkout(SUPER_SILENT, "master")
            sage: git.checkout(SUPER_SILENT, "-b","branch2")
            sage: with open("file","w") as f: f.write("version 2")
            sage: git.commit(SUPER_SILENT, "-am","conflicting commit")

            sage: git.is_ancestor_of('master', 'branch2')
            True
            sage: git.is_ancestor_of('branch2', 'master')
            False
            sage: git.is_ancestor_of('branch1', 'branch2')
            False
            sage: git.is_ancestor_of('master', 'master')
            True

        """
        return not self.rev_list(READ_OUTPUT, '{}..{}'.format(b, a)).splitlines()

    def has_uncommitted_changes(self):
        r"""
        Return whether there are uncommitted changes, i.e., whether there are
        modified files which are tracked by git.

        EXAMPLES:

        Create a :class:`GitInterface` for doctesting::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface, SILENT, SUPER_SILENT
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))

        An untracked file does not count towards uncommited changes::

            sage: os.chdir(config['git']['src'])
            sage: open('untracked','w').close()
            sage: git.has_uncommitted_changes()
            False

        Once added to the index it does::

            sage: git.add('untracked')
            sage: git.has_uncommitted_changes()
            True
            sage: git.commit(SUPER_SILENT, '-m', 'tracking untracked')
            sage: git.has_uncommitted_changes()
            False
            sage: with open('untracked','w') as f: f.write('version 0')
            sage: git.has_uncommitted_changes()
            True

        """
        return bool([line for line in self.status(READ_OUTPUT, porcelain=True).splitlines() if not line.startswith('?')])

    def untracked_files(self):
        r"""
        Return a list of file names for files that are not tracked by git and
        not ignored.

        EXAMPLES:

        Create a :class:`GitInterface` for doctesting::

            sage: import os
            sage: from sage.dev.git_interface import GitInterface, SILENT, SUPER_SILENT
            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: config = DoctestConfig()
            sage: git = GitInterface(config["git"], DoctestUserInterface(config["UI"]))

        An untracked file::

            sage: os.chdir(config['git']['src'])
            sage: git.untracked_files()
            []
            sage: open('untracked','w').close()
            sage: git.untracked_files()
            ['untracked']

         Directories are not displayed here::

            sage: os.mkdir('untracked_dir')
            sage: git.untracked_files()
            ['untracked']
            sage: open('untracked_dir/untracked','w').close()
            sage: git.untracked_files()
            ['untracked', 'untracked_dir/untracked']

        """
        return self.read_output('ls-files', other=True, exclude_standard=True).splitlines()

    def local_branches(self):
        r"""
        return the list of the local branches sorted by last commit time

        EXAMPLES::

            sage: dev.git.local_branches()
            ['first_branch', 'second_branch', 'master']
        """
        result = self.read_output('for-each-ref', 'refs/heads/',
                    sort='-committerdate', format="%(refname)").splitlines()
        return [head[11:] for head in result]

    def current_branch(self):
        r"""
        return the current branch

        EXAMPLES::

            sage: dev.git.current_branch()
            'first_branch'
        """
        try:
            branch = self.read_output('symbolic-ref', 'HEAD').strip()
            if branch.startswith('refs/heads/'):
                return branch[11:]
            int(branch, 16)
        except ValueError:
            raise RuntimeError('HEAD is bizarre!')
        else:
            raise ValueError('HEAD is detached')

    def _branch_printname(self, branchname):
        r"""
        return branchname, where ticket branches are specially recognized

        EXAMPLES::

            sage: dev.git._branch_printname('first_branch')
            'first_branch'
            sage: dev.git._branch_printname('t/12345')
            '#12345'
            sage: dev.git._branch_printname('ticket/12345')
            '#12345'
        """
        if branchname.startswith('ticket/'):
            return '#' + branchname[7:]
        elif branchname.startswith('t/'):
            return '#' + branchname[2:]
        else:
            return branchname

    def _local_to_remote_name(self, branchname):
        r"""
        convert local branch name to 'canonical' remote branch name

        EXAMPLES::

            sage: dev.git._local_to_remote_name('padics/feature')
            'g/padics/feature'
            sage: dev.git._local_to_remote_name('t/12345')
            'u/doctest/ticket/12345'
            sage: dev.git._local_to_remote_name('ticket/12345')
            'u/doctest/ticket/12345'
            sage: dev.git._local_to_remote_name('u/doctest0/ticket/12345')
            'u/doctest0/ticket/12345'
            sage: dev.git._local_to_remote_name('some/local/project')
            'u/doctest/some/local/project'
        """
        if branchname in ("release", "beta", "master"):
            return branchname
        x = branchname.split('/')
        if is_local_group_name(x):
            if is_ticket_name(x[1:]):
                return '/'.join(('g', x[0], normalize_ticket_name(x[1:])))
            return '/'.join(['g']+x)
        elif is_ticket_name(x):
            return '/'.join(('u', self._sagedev.trac._username,
                normalize_ticket_name(x)))
        elif is_remote_user_name(x):
            return branchname
        else:
            return '/'.join(('u', self._sagedev.trac._username, branchname))

    def _remote_to_local_name(self, branchname):
        r"""
        convert remote branch name to 'canonical' local branch name

        EXAMPLES::

            sage: dev.git._remote_to_local_name('g/padics/feature')
            'padics/feature'
            sage: dev.git._remote_to_local_name('u/doctest/t/12345')
            'ticket/12345'
            sage: dev.git._remote_to_local_name('u/doctest/ticket/12345')
            'ticket/12345'
            sage: dev.git._remote_to_local_name('u/doctest0/ticket/12345')
            'u/doctest0/ticket/12345'
            sage: dev.git._remote_to_local_name('u/doctest/some/remote/project')
            'some/remote/project'
        """
        if branchname in ("release", "beta", "master"):
            return branchname
        x = branchname.split('/')
        if is_remote_group_name(x):
            if is_ticket_name(x[2:]):
                return '/'.join((x[1], normalize_ticket_name(x[2:])))
            return '/'.join(x[1:])
        elif is_remote_user_name(x):
            if x[1] != self._sagedev.trac._username:
                return branchname
            elif is_ticket_name(x[2:]):
                return normalize_ticket_name(x[2:])
            return '/'.join(x[2:])
        raise ValueError("not a valid remote branch name")

    def branch_exists(self, branch):
        r"""
        returns the commit id of the local branch, or ``None`` if
        branch does not exist

        EXAMPLES::

            sage: git = dev.git
            sage: git.branch_exists("first_branch")          # random
            '087e1fdd0fe6f4c596f5db22bc54567b032f5d2b'
            sage: int(git.branch_exists("first_branch"), 16) # random
            48484595766010161581593150175214386043155340587L
            sage: type(git.branch_exists("first_branch"))
            <type 'str'>
            sage: len(git.branch_exists("first_branch"))
            40
            sage: git.branch_exists("asdlkfjasdlf")
        """
        ref = "refs/heads/%s"%branch
        return self.ref_exists("refs/heads/%s"%branch)

    def ref_exists(self, ref):
        r"""
        returns the commit id of the ref, or ``None`` if
        branch does not exist

        EXAMPLES::

            sage: git = dev.git
            sage: git.ref_exists("refs/tags/test_tag")          # random
            'abdb32da3a1e50d4677e4760eda9433ac8b45414'
            sage: int(git.ref_exists("refs/tags/test_tag"), 16) # random
            981125714882459973971230819971657414365142078484L
            sage: type(git.ref_exists("refs/tags/test_tag"))
            <type 'str'>
            sage: len(git.ref_exists("refs/tags/test_tag"))
            40
            sage: git.ref_exists("refs/tags/asdlkfjasdlf")
        """
        try:
            self.execute("show-ref", ref, quiet=True, verify=True)
        except GitError:
            return None
        return self.read_output("show-ref", ref, hash=True, verify=True).strip()

    def create_branch(self, branchname, basebranch=None, remote_branch=True):
        r"""
        creates branch ``branchname`` based off of ``basebranch`` or the
        current branch if ``basebranch`` is ``None``

        EXAMPLES::

            sage: from sage.dev.sagedev import SageDev, doctest_config
            sage: git = SageDev(doctest_config()).git
            sage: git.create_branch("third_branch")
            sage: git.branch_exists("third_branch") == git.branch_exists("first_branch")
            True
            sage: git.create_branch("fourth_branch", "second_branch")
            sage: git.branch_exists("fourth_branch") == git.branch_exists("second_branch")
            True
        """
        if branchname in ("t", "ticket", "all", "dependencies", "commit",
                "release", "beta", "master"):
            raise ValueError("bad branchname")
        if self.branch_exists(branchname):
            raise ValueError("branch already exists")

        if basebranch is None:
            ret = self.execute("branch", branchname)
        else:
            ret = self.execute("branch", branchname, basebranch)

        if remote_branch is True:
            remote_branch = self._local_to_remote_name(branchname)
        if remote_branch:
            self._sagedev._remote[branchname] = remote_branch

        if ret: # return non-zero exit codes
            return ret

    def rename_branch(self, oldname, newname):
        r"""
        renames branch ``oldname`` to ``newname``

        EXAMPLES::

            sage: from sage.dev.sagedev import SageDev, doctest_config
            sage: git = SageDev(doctest_config()).git
            sage: bool(git.branch_exists("third_branch"))
            False
            sage: git.rename_branch("first_branch", "third_branch")
            sage: bool(git.branch_exists("first_branch"))
            False
            sage: bool(git.branch_exists("third_branch"))
            True
            sage: git.rename_branch("third_branch", "second_branch")
            fatal: A branch named 'second_branch' already exists.
        """
        self.execute("branch", oldname, newname, m=True)

    def fetch_project(self, group, branchname):
        raise NotImplementedError

    def switch_branch(self, branchname, detached = False):
        r"""
        switch to ``branchname`` in a detached state if ``detached`` is
        set to True

        EXAMPLES::

            sage: from sage.dev.sagedev import SageDev, doctest_config
            sage: git = SageDev(doctest_config()).git
            sage: git.current_branch()
            'first_branch'
            sage: git.switch_branch('second_branch')
            Switched to branch 'second_branch'
            sage: git.current_branch()
            'second_branch'
            sage: git.branch_exists('third_branch')
            sage: git.switch_branch('third_branch')
            Switched to branch 'third_branch'
            sage: git.branch_exists('third_branch') # random
            '5249e7a56067e9f30244930192503d502558b6c3'
            sage: git.switch_branch('first_branch', detached=True)
            Note: checking out 'first_branch'.
            <BLANKLINE>
            You are in 'detached HEAD' state. You can look around, make experimental
            changes and commit them, and you can discard any commits you make in this
            state without impacting any branches by performing another checkout.
            <BLANKLINE>
            If you want to create a new branch to retain commits you create, you may
            do so (now or later) by using -b with the checkout command again. Example:
            <BLANKLINE>
              git checkout -b new_branch_name
            <BLANKLINE>
            HEAD is now at ... edit the testfile differently
        """
        move = None
        if self.has_uncommitted_changes():
            move = self.save_uncommitted_changes()

        if not detached and self.branch_exists(branchname) is None:
            if self.create_branch(branchname) is not None:
                raise RuntimeError("could not create new branch")

        self.execute("checkout", branchname, detach=detached)

        if move:
            self.unstash_changes()

    def unstash_changes(self):
        try:
            self.execute_silent("stash", "apply")
            self.execute_silent("stash", "drop")
        except GitError:
            self.execute_silent("reset", hard=True)
            self._UI.show("Changes did not apply cleanly to the new branch. "+
                          "They are now in your stash.")

    def vanilla(self, release=True):
        r"""
        switch to released version of sage
        """
        if release is False:
            release = "master"
        elif release is True:
            release = "release"
        else:
            release = str(release)
            if is_release_name(release.split('.')):
                self.execute('fetch', 'origin', tags=True)
                release = self.ref_exists('refs/tags/%s'%release)
                if release is None:
                    raise ValueError("was unable to find desired release")
        self.switch_branch(release)

    def abandon(self, branchname):
        r"""
        move branch to trash

        EXAMPLES::

            sage: from sage.dev.sagedev import SageDev, doctest_config
            sage: git = SageDev(doctest_config()).git
            sage: git.abandon('second_branch')
            sage: git.local_branches()
            ['first_branch', 'abandoned/second_branch', 'master']
        """
        trashname = "abandoned/" + branchname
        oldtrash = self.branch_exists(trashname)
        if oldtrash is not None:
            self._UI.show("Overwriting %s in trash"%oldtrash)
        self.rename_branch(branchname, trashname)
        # Need to delete remote branch (and have a hook move it to /g/abandoned/ and update the trac symlink)
        #remotename = self._remote[branchname]

    @classmethod
    def is_atomic_name(x):
        r"""
        returns true if x is a valid atomic branch name

        EXAMPLES::

            sage: from sage.dev.git_interface import is_atomic_name
            sage: is_atomic_name(["branch"])
            True
            sage: is_atomic_name(["/branch"])
            False
            sage: is_atomic_name(["refs","heads","branch"])
            False
            sage: is_atomic_name([""])
            False
            sage: is_atomic_name(["u"])
            False
            sage: is_atomic_name(["1234"])
            True
        """
        if len(x) != 1:
            return False
        if '/' in x[0]:
            return False
        return x[0] not in ("t", "ticket", "u", "g", "abandoned","")

    @classmethod
    def is_ticket_name(x):
        r"""
        returns true if x is a valid ticket branch name

        EXAMPLES::

            sage: from sage.dev.git_interface import is_ticket_name
            sage: is_ticket_name(["t", "1234"])
            True
            sage: is_ticket_name(["u", "doctest", "branch"])
            False
            sage: is_ticket_name(["padics", "feature"])
            False
            sage: is_ticket_name(["ticket", "myticket"])
            False
            sage: is_ticket_name(["ticket", "9876"])
            True
        """
        if len(x) != 2:
            return False
        if x[0] not in ('ticket', 't'):
            return False
        return x[1].isdigit()

    @classmethod
    def is_local_group_name(x):
        r"""
        returns true if x is a valid local group branch name

        EXAMPLES::

            sage: from sage.dev.git_interface import is_local_group_name
            sage: is_local_group_name(["padic", "feature"])
            True
            sage: is_local_group_name(["g", "padic", "feature"])
            False
            sage: is_local_group_name(["padic", "feature", "1234"])
            False
            sage: is_local_group_name(["padic", "ticket", "1234"])
            True
        """
        if len(x) == 0:
            return False
        if not is_atomic_name(x[0:1]):
            return False
        if len(x) == 2:
            return is_atomic_name(x[1:])
        else:
            return is_ticket_name(x[1:])

    @classmethod
    def is_remote_group_name(x):
        r"""
        returns true if x is a valid remote group branch name

        EXAMPLES::

            sage: from sage.dev.git_interface import is_remote_group_name
            sage: is_remote_group_name(["padic", "feature"])
            False
            sage: is_remote_group_name(["g", "padic", "feature"])
            True
            sage: is_remote_group_name(["g", "padic", "feature", "1234"])
            False
            sage: is_remote_group_name(["g", "padic", "ticket", "1234"])
            True
            sage: is_remote_group_name(["u", "doctest", "ticket", "1234"])
            False
        """
        if len(x) < 3:
            return False
        if x[0] != "g":
            return False
        return is_local_group_name(x[1:])

    @classmethod
    def is_remote_user_name(x):
        r"""
        returns true if x is a valid remote user branch name

        EXAMPLES::

            sage: from sage.dev.git_interface import is_remote_user_name
            sage: is_remote_user_name(["u", "doctest", "ticket", "12345"])
            True
            sage: is_remote_user_name(["u", "doctest", "ticket", ""])
            False
            sage: is_remote_user_name(["u", "doctest"])
            False
            sage: is_remote_user_name(["g", "padic", "feature"])
            False
            sage: is_remote_user_name(["u", "doctest", "feature"])
            True
        """
        if len(x) < 3:
            return False
        if x[0] != "u":
            return False
        return all(x[1:])

    @classmethod
    def is_release_name(x):
        r"""
        returns true if x is a valid release name

        WARNING: this does not imply the existence of such a release

        EXAMPLES::

            sage: from sage.dev.git_interface import is_release_name
            sage: is_release_name(['5', '2', '7'])
            True
            sage: is_release_name(['6', '-2'])
            False
            sage: is_release_name(['6', 'beta0'])
            True
            sage: is_release_name(['7', 'rc'])
            False
            sage: is_release_name(['7', 'rc1'])
            True
        """
        for v in x[:-1]:
            try:
                if int(v) < 0:
                    return False
            except ValueError:
                return False
        v = x[-1]
        if v.startswith('alpha'):
            v = v[5:]
        elif v.startswith('beta'):
            v = v[4:]
        elif v.startswith('rc'):
            v = v[2:]
        try:
            return int(v) >= 0
        except ValueError:
            return False

    @classmethod
    def normalize_ticket_name(x):
        r"""
        returns the normalized ticket branch name for x

        WARNING: it does not check to see if x is a valid ticket branch name

        EXAMPLES::

            sage: from sage.dev.git_interface import normalize_ticket_name
            sage: normalize_ticket_name(["t", "12345"])
            'ticket/12345'
            sage: normalize_ticket_name(["cow", "goes", "moo"])
            'ticket/goes'
            sage: normalize_ticket_name(["branch"])
            Traceback (most recent call last):
            ...
            IndexError: list index out of range
        """
        return '/'.join(('ticket', x[1]))

for git_cmd_ in (
        "add",
        "am",
        "apply",
        "bisect",
        "branch",
        "checkout",
        "clean",
        "clone",
        "commit",
        "diff",
        "fetch",
        "format_patch",
        "grep",
        "init",
        "log",
        "merge",
        "mv",
        "pull",
        "push",
        "rebase",
        "reset",
        "rev_list",
        "rm",
        "show",
        "stash",
        "status",
        "tag"
        ):
    def create_wrapper(git_cmd__):
        r"""
        Create a wrapper for `git_cmd__`.

        EXAMPLES::

            sage: from sage.dev.test.config import DoctestConfig
            sage: from sage.dev.test.user_interface import DoctestUserInterface
            sage: from sage.dev.git_interface import GitInterface
            sage: GitInterface(DoctestConfig(), DoctestUserInterface()).status()

        """
        git_cmd = git_cmd__.replace("_","-")
        def meth(self, *args, **kwds):
            r"""
            Call `git {0}`.

            If `args` contains ``SILENT``, then output to stdout is supressed.

            If `args` contains ``SUPER_SILENT``, then output to stdout and stderr
            is supressed.

            OUTPUT:

            Returns ``None`` unless `args` contains ``READ_OUTPUT``; in that case,
            the commands output to stdout is returned.

            See :meth:`execute` for more information.

            EXAMPLES:

                sage: dev.git.{1}() # not tested

            """.format(git_cmd, git_cmd__)
            args = list(args)
            if len([arg for arg in args if arg in (SILENT, SUPER_SILENT, READ_OUTPUT)]) > 1:
                raise ValueError("at most one of SILENT, SUPER_SILENT, READ_OUTPUT allowed")
            if SILENT in args:
                args.remove(SILENT)
                return self.execute_silent(git_cmd, *args, **kwds)
            elif SUPER_SILENT in args:
                args.remove(SUPER_SILENT)
                return self.execute_supersilent(git_cmd, *args, **kwds)
            elif READ_OUTPUT in args:
                args.remove(READ_OUTPUT)
                return self.read_output(git_cmd, *args, **kwds)
            else:
                return self.execute(git_cmd, *args, **kwds)
        return meth
    setattr(GitInterface, git_cmd_, create_wrapper(git_cmd_))