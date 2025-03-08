# TODO

## Next release

- N/A

## Future

- test how pyright behaves on all ast nodes
- handle multiple assignment better (`x = y = z`)
- consider using a proper AST node visitor for unquoting type expressions.
- double check privacy conventions against provided config
    - https://typing.readthedocs.io/en/latest/spec/distributing.html#stub-files
    - https://typing.readthedocs.io/en/latest/guides/writing_stubs.html
- check if we should do something special for default value assignment in
  function signatures, TypeAlias and other special cases
- add config to disable type expression conversion (and maybe Annotated[] or comment based opt-out)
- consider obeying typing.no_type_check
- allow filtering out whole module files
- redirect all prints to a global logger class that can be directed to other output if the tool is started from code
- add mypy type stub generator
  - do not forget deps
- change eval command commandline to not hardcode pyright and mypy in "all" (just remove "all")
- think about using pydantic for Config parsing & help metadata
- implement privacy in dubstub implementation
- consider evaluating all exception raise points and wrapping them in custom sensible errors.
  Note: Already attempted once and considered not important enough.
