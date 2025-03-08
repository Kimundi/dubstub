from tomli_w import dumps as dumps  # pylint: disable=unused-import

try:
    from tomli import loads as loads  # pylint: disable=unused-import
except ImportError:
    from tomllib import loads as loads  # type: ignore
