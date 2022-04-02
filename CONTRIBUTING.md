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

- ci
- feat
- fix
- perf
- refactor
- chore
- other

Further the first letter after the tag must be upper case

Example:

`feat: New Button which does something`
