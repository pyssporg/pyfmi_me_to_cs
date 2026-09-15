"""Custom exceptions for the cs-fmu-packager tool."""


class CsFmuPackagerError(Exception):
    """Base exception for all cs-fmu-packager errors."""


class SpecValidationError(CsFmuPackagerError):
    """Raised when the package specification is invalid."""


class FmuInspectionError(CsFmuPackagerError):
    """Raised when an internal FMU cannot be read or validated."""


class MappingError(CsFmuPackagerError):
    """Raised when variable mapping between spec and FMUs fails."""


class CodegenError(CsFmuPackagerError):
    """Raised when C code generation fails."""


class BuildError(CsFmuPackagerError):
    """Raised when CMake build of wrapper code fails."""


class PackagingError(CsFmuPackagerError):
    """Raised when final FMU assembly fails."""