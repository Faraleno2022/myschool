"""
Expose submodules so Django's test loader can find tests when importing
`paiements.tests`.

Django imports the tests package (paiements.tests) and loads tests from the
module object; it does not automatically recurse into submodules unless they
are imported here.
"""

# Import test modules
from . import test_allocation  # noqa: F401
