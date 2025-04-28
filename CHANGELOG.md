# 1.4.1

- Rewrite handling of attributes that have been extracted from `__init__` methods.
  They are now subject to the same transformations as normal attributes.

# 1.4

- Rewrite heuristic for discovering (un)used names in a module to handle more than just imports

# 1.3.1

- Fix class attributes being inserted before doc strings

# 1.3

- Add: Added class attribute extraction from `__init__()` methods.

# 1.2

- Add: Added `--filter` argument for `dubstub diff`.

# 1.1.1

- Minor fixes

# 1.1.1

- Fix tests

# 1.1.0

- Added `mypy` stubgen support for the `eval` command

# 1.0.1

- Fix bug in pyright `eval` command

# 1.0

- Initial release
