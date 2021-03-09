class TriggerObject:
    def __init__(self, initial_value=False, callback=False):
        self._value = initial_value
        self._callbacks = []
        if callback:
            self._callbacks.append(callback)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value):
        self._value = new_value
        self._notify_observers(new_value)

    def _notify_observers(self, new_value):
        for callback in self._callbacks:
            callback(new_value)

    def register_callback(self, callback):
        self._callbacks.append(callback)