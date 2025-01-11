# CJH trying to put fairly complex mechanism definitions outside physics.py
# 2024 1228
import wpilib


# Simplified dictionary wrapper for Mechanism2d
class MechTracker:
    def __init__(self, *, length, width, height, view):
        """
        Initialize the MechTracker with dimensions and a specific view (side or top).

        :param length: Length of the mechanism.
        :param width: Width of the mechanism (for top view).
        :param height: Height of the mechanism (for side view).
        :param view: View of the mechanism ('side' or 'top').
        """
        self.length = length
        self.width = width
        self.height = height
        if view == 'side':
            self.mechanism = wpilib.Mechanism2d(length, height)
        elif view == 'top':
            self.mechanism = wpilib.Mechanism2d(length, width)
        else:
            raise ValueError("View must be 'side' or 'top'.")

        self.components = {}

    def getRoot(self, name, x, y):
        root = self.mechanism.getRoot(name, x, y)
        if name in self.components:
            raise ValueError(f"Component '{name}' already exists in the components dictionary.")
        self.components[name] = {'root': root, 'ligaments': []}
        print(f"DEBUG: Added root '{name}' at ({x}, {y})")
        return root

    def appendLigament(self, parent_name, name, length, angle, weight, color):
        if parent_name not in self.components:
            raise ValueError(f"Parent '{parent_name}' not found.")

        parent = self.components[parent_name].get('root') or self.components[parent_name].get('ligament')
        if not parent:
            raise ValueError(f"Parent '{parent_name}' does not have a valid root or ligament.")
        
        ligament = parent.appendLigament(name, length, angle, weight, wpilib.Color8Bit(color))
        self.components[parent_name]['ligaments'].append(name)
        self.components[name] = {
            'ligament': ligament,
            'ligaments': [],
            'length': length,  # Store the initial length
            'angle': angle,  # Store the initial angle
            'weight': weight,  # Store the weight
            'color': color  # Store the color
        }
        print(
            f"DEBUG: Added ligament '{name}' under parent '{parent_name}' with length {length}, angle {angle}, weight {weight}, color {color}")
        return ligament


# Initialize the mechanism trackers
length = 40 #joshsugino 1/11/25: eventuallly make these constants. I think the goal is to have a "sim" constants class in constants.py (?)
width = length
height = 60
side_mech = MechTracker(length=length, width=width, height=height, view='side')
top_mech = MechTracker(length=length, width=width, height=height, view='top')

# side view of elevator mechanism
elevator_length = 20
elevator_height = 50
bar_width = 10

elevator_offset_x = (length - elevator_length) / 2
elevator_offset_y = (height - elevator_height) / 2
elevator_base = side_mech.getRoot("elevator", elevator_offset_x, elevator_offset_y)

side_mech.appendLigament("elevator", "elevator_bottom", elevator_length, 0, bar_width, wpilib.Color.kRed)
side_mech.appendLigament("elevator_bottom", "elevator_right", elevator_height, 90, bar_width, wpilib.Color.kRed)
side_mech.appendLigament("elevator_right", "elevator_top", elevator_length, 90, bar_width, wpilib.Color.kRed)
side_mech.appendLigament("elevator_top", "elevator_left", elevator_height, 90, bar_width, wpilib.Color.kRed)

# top view - looking down front is on the right,  right is on the bottom.  remember - angles are relativeto parent!

#joshsugino 1/20/25 - note: I didn't include the top view of the elevator, because nothing would actually change in the animation.

chassis_length = 28
bar_width = 12
chassis_offset = (length - chassis_length) / 2
chassis_base_top = top_mech.getRoot("chassis_base_top", chassis_offset, chassis_offset)
top_mech.appendLigament("chassis_base_top", "chassis_right", chassis_length, 0, bar_width, wpilib.Color.kGray)
top_mech.appendLigament("chassis_right", "chassis_front", chassis_length, 90, bar_width, wpilib.Color.kDodgerBlue)
top_mech.appendLigament("chassis_front", "chassis_left", chassis_length, 90, bar_width, wpilib.Color.kOrange)
top_mech.appendLigament("chassis_left", "chassis_back", chassis_length, 90, bar_width, wpilib.Color.kGreen)
top_mech.appendLigament("chassis_right", "Intake", 10, 180, 10, wpilib.Color.kDarkRed)

swerve_offset = 4  # try to put the wheels somewhere that looks good
swerves = ['swerve_right', 'swerve_front', 'swerve_left', 'swerve_back']
colors = [wpilib.Color.kGreen, wpilib.Color.kOrange, wpilib.Color.kYellow, wpilib.Color.kBlue]
offsets = [(chassis_offset + swerve_offset, chassis_offset + swerve_offset ),
           (chassis_offset + chassis_length - swerve_offset, chassis_offset + swerve_offset),
           (chassis_offset + chassis_length - swerve_offset, chassis_offset + chassis_length - swerve_offset),
           (chassis_offset + swerve_offset, chassis_offset + chassis_length - swerve_offset)]
for color, offset, swerve in zip(colors, offsets, swerves):
    top_mech.getRoot(swerve, offset[0], offset[1])
    # if you want things to rotate about the center you have to fake it
    top_mech.appendLigament(swerve, swerve + 'lig_front', 2, 45, 10, color)
    top_mech.appendLigament(swerve, swerve + 'lig_back', 2, 225, 10, wpilib.Color.kWhite)

# Push to SmartDashboard
wpilib.SmartDashboard.putData("Side Mechanism", side_mech.mechanism)
wpilib.SmartDashboard.putData("Top Mechanism", top_mech.mechanism)

# Debugging output
print("DEBUG: Side Mechanism Components:")
for name, data in side_mech.components.items():
    print(f"side:  {name}: {data}")

print("DEBUG: Top Mechanism Components:")
for name, data in top_mech.components.items():
    print(f"top:  {name}: {data}")
