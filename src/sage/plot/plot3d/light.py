r"""

"""
from sage.structure.sage_object import SageObject
from sage.plot.colors import Color

class Light(SageObject):
    def __init__(self, color='white'):
        self.color = Color(color)

    def scenetree_json(self):
        return {'type': 'light', 'color': int(self.color)}

class AmbientLight(Light):
    def __init__(self, color='white'):
        super(AmbientLight, self).__init__(color=color)

    def scenetree_json(self):
        d = super(AmbientLight, self).scenetree_json()
        d.update(light_type='ambient')
        return d

class PositionLight(Light):
    def __init__(self, position, color='white', intensity=1.0, fixed='camera'):
        super(PositionLight, self).__init__(color=color)
        self.intensity = intensity
        self.position = position
        self.fixed = fixed

    def scenetree_json(self):
        d = super(PositionLight, self).scenetree_json()
        d.update(intensity=self.intensity, position=self.position, fixed=self.fixed)
        return d

class DirectionalLight(PositionLight):
    def __init__(self, position, color='white', intensity=1.0, fixed='camera'):
        super(DirectionalLight, self).__init__(position=position, color=color, intensity=intensity, fixed=fixed)

    def scenetree_json(self):
        d = super(DirectionalLight, self).scenetree_json()
        d.update(light_type='directional')
        return d

class PointLight(PositionLight):
    def __init__(self, position, color='white', intensity=1.0, distance=0, fixed='camera'):
        super(PointLight, self).__init__(position=position, color=color, intensity=intensity, fixed=fixed)
        self.distance = distance

    def scenetree_json(self):
        d = super(PointLight, self).scenetree_json()
        d.update(light_type='point', distance=self.distance)
        return d

class SpotLight(PointLight):
    def __init__(self, position, color='white', intensity=1.0, distance=0, fixed='camera', angle=1.0471, exponent=10.0):
        """
        default angle is approximately pi/3
        """
        super(SpotLight, self).__init__(position=position, color=color, intensity=intensity, distance=distance, fixed=fixed)
        self.angle = angle
        self.exponent = exponent

    def scenetree_json(self):
        d = super(SpotLight, self).scenetree_json()
        d.update(light_type='spot', angle = self.angle, exponent = self.exponent)
        return d

lights = {
    'colors': [
        AmbientLight(color=(0.312,0.188,0.4)),
        DirectionalLight(position=(1,0,1), color=(0.8, 0, 0), fixed='camera'),
        DirectionalLight(position=(1,1,1), color=(0, 0.8, 0), fixed='camera'),
        DirectionalLight(position=(0,1,1), color=(0, 0, 0.8), fixed='camera'),
        DirectionalLight(position=(-1,-1,-1), color=(.9,.7,.9), fixed='camera'),
        ],
    'shades': [
        AmbientLight(color=(.4, .4, .4)),
        DirectionalLight(position=(0,1,1), color=(.35, .35, .35), fixed='camera'),
        DirectionalLight(position=(0,0,1), color=(.35, .35, .35), fixed='camera'),
        DirectionalLight(position=(1,1,1), color=(.25, .25, .25), fixed='camera'),
        DirectionalLight(position=(-1,-1,-1), color=(.7,.7,.7), fixed='camera'),
        ],
    }
