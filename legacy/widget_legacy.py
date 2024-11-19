from icecream import ic


class WidgetLegacy:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.exports = ['render']

    @classmethod
    def create(cls, **kwargs):
        ic(f'Calling proxy Create with args: {kwargs}')
        return cls(**kwargs)

    def render(self, condition):
        return print(f'Rendered {self.kwargs}')
