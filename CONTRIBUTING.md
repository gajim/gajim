# Project

If you want to create a fork and use an external account (Github, Google) drop us a message at the Gajim support [group chat](xmpp:gajim@conference.gajim.org?join) so we can give you the necessary rights

## Versioning

┌────── Major (Will not change unless we switch GTK version)  
│ ┌───── Minor (Changes when new features are introduced  
│ │ ┌──── Micro (Used for hotfixes and small changes)  
│ │ │ ┌─── Only used while developing  
│ │ │ │  
│ │ │ │  
│ │ │ │  
│ │ │ │  
1.3.3-dev1

## Branches

Currently there is only one stable/development branch - master.
The master branch must always be in a releasable state.

Development for bigger changes need to happen in feature branches or forks.

Previously the project maintained multiple versions of Gajim in
different stable branches, but from Gajim 1.4.0 on this approach was changed
to lower the maintenance burden and release faster.


# Commit Messages

If you are not familiar with Git please read the [HowTo](https://dev.gajim.org/gajim/gajim/wikis/development/howtogit)

A good article regarding [good commit messages](https://chris.beams.io/posts/git-commit/)

Every commit message must be prefixed with one of the following tags:

Changelog relevant

- feat      (a new feature was added)
- fix       (something was fixed)
- perf      (performance related changes)
- imprv     (improvements)
- change    (existing functionality was changed)

Prefixes for development

- new       (new code, but the end user will not notice)
- ci        (ci related changes)
- cq        (code quality changes e.g. formatting, typing, codestyle)
- cfix      (code fixes which should not show up in the changelog)
- refactor  (code was changed, but the end user will not notice)
- chore     (reoccuring tasks which need to be done)
- release   (only used for release commits)
- other

Further the first letter after the tag must be upper case

Example:

`feat: New Button which does something`

# Use pre-commit

Execute the following inside the repositor dir

    $ pip install pre-commit
    $ pre-commit install

Now pre-commit will run various checks before code can be committed.

To update to the newest versions

    $ pre-commit autoupdate

# Man Pages

Man pages are written in markdown and converted with pandoc

While developing this command is useful to preview the manpage

    $ pandoc gajim.1.md -s -t man | /usr/bin/man -l -

To convert the markdown

    $ pandoc gajim.1.md -s -t man -o gajim.1
