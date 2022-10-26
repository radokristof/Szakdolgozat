class NodeNotFoundException(Exception):
    def __init__(self, message):
        super().__init__(message)

class NetworkSourceDestinationException(Exception):
    def __init__(self, message):
        super().__init__(message)

class NetworkMultipleDefinitionException(Exception):
    def __init__(self, message):
        super().__init__(message)

class PlaybookRunException(Exception):
    def __init__(self, message):
        super().__init__(message)
