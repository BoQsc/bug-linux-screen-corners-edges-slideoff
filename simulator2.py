#!/usr/bin/env python3
import tkinter as tk
import subprocess
import platform

# Canvas dimensions and coordinate ranges
CANVAS_WIDTH = 500
CANVAS_HEIGHT = 500
MARGIN = 20  # Padding around the drawing area
X_MIN, X_MAX = 0.0, 1.0   # Normalized input range
Y_MIN, Y_MAX = 0.0, 3.0   # Normalized output range
POINT_RADIUS = 6
DELTA_Y = 0.1  # Amount to adjust the y-value of control points

# Predefined Windows-like preset (4 points)
WINDOWS_CURVE = [
    [0.0, 0.0],   # Low speed (min)
    [0.3, 0.3],   # Early acceleration start
    [0.6, 1.2],   # Advanced acceleration
    [1.0, 2.5],   # High speed cap
]

def to_canvas_coords(x, y):
    """Map (x, y) in [X_MIN,X_MAX]x[Y_MIN,Y_MAX] to canvas pixel coordinates with padding."""
    drawable_width = CANVAS_WIDTH - 2 * MARGIN
    drawable_height = CANVAS_HEIGHT - 2 * MARGIN
    canvas_x = MARGIN + (x - X_MIN) / (X_MAX - X_MIN) * drawable_width
    canvas_y = CANVAS_HEIGHT - MARGIN - (y - Y_MIN) / (Y_MAX - Y_MIN) * drawable_height
    return canvas_x, canvas_y

def to_function_coords(canvas_x, canvas_y):
    """Map canvas pixel coordinates (with padding) back to function coordinates."""
    drawable_width = CANVAS_WIDTH - 2 * MARGIN
    drawable_height = CANVAS_HEIGHT - 2 * MARGIN
    x = (canvas_x - MARGIN) / drawable_width * (X_MAX - X_MIN) + X_MIN
    y = (CANVAS_HEIGHT - MARGIN - canvas_y) / drawable_height * (Y_MAX - Y_MIN) + Y_MIN
    return x, y

class CurveEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Custom Pointer Acceleration Curve Editor")

        # Create variables for checkboxes
        self.use_windows_curve = tk.BooleanVar(value=False)
        self.enable_nonlinear_boost = tk.BooleanVar(value=False)
        self.enable_acceleration_cap = tk.BooleanVar(value=False)
        self.human_labels = tk.BooleanVar(value=True)
        # New: lock the low-speed control point (index 0)
        self.lock_low_speed = tk.BooleanVar(value=True)

        # Maintain a set of indices for selected control points
        self.selected_indices = set()

        # Frame for options with some padding
        options_frame = tk.Frame(self, padx=10, pady=10)
        options_frame.pack(pady=5)

        # Checkboxes for curve options
        self.win_chk = tk.Checkbutton(
            options_frame, text="Use Windows-like curve",
            variable=self.use_windows_curve, command=self.update_curve_from_options
        )
        self.win_chk.grid(row=0, column=0, sticky="w", padx=5)

        self.boost_chk = tk.Checkbutton(
            options_frame, text="Enable Non-linear Boost",
            variable=self.enable_nonlinear_boost, command=self.update_curve_from_options
        )
        self.boost_chk.grid(row=0, column=1, sticky="w", padx=5)

        self.cap_chk = tk.Checkbutton(
            options_frame, text="Enable Acceleration Cap",
            variable=self.enable_acceleration_cap, command=self.update_curve_from_options
        )
        self.cap_chk.grid(row=0, column=2, sticky="w", padx=5)

        self.human_label_chk = tk.Checkbutton(
            options_frame, text="Human Readable Labels",
            variable=self.human_labels, command=self.draw_grid
        )
        self.human_label_chk.grid(row=0, column=3, sticky="w", padx=5)

        # New: Checkbox to lock the low speed (min) control point
        self.lock_low_chk = tk.Checkbutton(
            options_frame, text="Lock Low speed (min)",
            variable=self.lock_low_speed
        )
        self.lock_low_chk.grid(row=0, column=4, sticky="w", padx=5)

        # Buttons for adjusting selected control points
        self.increase_btn = tk.Button(options_frame, text="Increase All", command=self.increase_all_points)
        self.increase_btn.grid(row=1, column=0, padx=5, pady=5)

        self.decrease_btn = tk.Button(options_frame, text="Decrease All", command=self.decrease_all_points)
        self.decrease_btn.grid(row=1, column=1, padx=5, pady=5)

        # New: Drop-down to select pointer device (Linux only)
        self.device_name_var = tk.StringVar()
        available_devices = self.get_pointer_devices()
        if available_devices:
            self.device_name_var.set(available_devices[0])
        else:
            self.device_name_var.set("No pointer device found")
        device_label = tk.Label(options_frame, text="Pointer Device:")
        device_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.device_menu = tk.OptionMenu(options_frame, self.device_name_var, *available_devices)
        self.device_menu.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        self.canvas = tk.Canvas(self, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="white")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)

        # Label to display control point values
        self.values_label = tk.Label(self, text="", font=("Arial", 10))
        self.values_label.pack(pady=5)

        # Explanatory notes
        explanation = (
            "Instructions:\n"
            " - Click on a control point to select it. Clicking without SHIFT selects only that point; "
            "clicking with SHIFT toggles selection (for multiple selection).\n"
            " - Click away from any control point to clear the selection.\n"
            " - Drag a control point to move it (locked points cannot be moved).\n"
            " - Use the Increase/Decrease buttons to adjust only the selected control points.\n\n"
            "Toggle the other options to test various findings from reverse-engineering Windows pointer acceleration."
        )
        self.explanation_label = tk.Label(self, text=explanation, font=("Arial", 9),
                                          justify="left", wraplength=CANVAS_WIDTH - 2 * MARGIN)
        self.explanation_label.pack(pady=5)

        # Start with a default curve (a simple 3-point curve as the baseline)
        self.points = [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
        self.drag_data = {"point_index": None, "offset_x": 0, "offset_y": 0}

        self.draw_grid()
        self.update_curve_from_options()

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def get_pointer_devices(self):
        """Return a sorted list of available pointer device names (Linux only).
           Priority: USB > Mouse > Optical."""
        try:
            output = subprocess.check_output(["xinput", "list", "--name-only"]).decode("utf-8")
            devices = output.splitlines()
            def device_priority(name):
                n = name.lower()
                if "usb" in n:
                    return 1
                elif "mouse" in n:
                    return 2
                elif "optical" in n:
                    return 3
                else:
                    return 100
            pointer_devices = [d for d in devices if "mouse" in d.lower() or "touchpad" in d.lower()]
            pointer_devices.sort(key=device_priority)
            return pointer_devices
        except Exception as e:
            print(f"Error retrieving pointer devices: {e}")
            return []

    def draw_grid(self):
        self.canvas.delete("grid")
        drawable_width = CANVAS_WIDTH - 2 * MARGIN
        drawable_height = CANVAS_HEIGHT - 2 * MARGIN
        for i in range(11):
            x = MARGIN + i / 10 * drawable_width
            self.canvas.create_line(x, MARGIN, x, CANVAS_HEIGHT - MARGIN, fill="#ddd", tags="grid")
        for i in range(11):
            y = MARGIN + i / 10 * drawable_height
            self.canvas.create_line(MARGIN, y, CANVAS_WIDTH - MARGIN, y, fill="#ddd", tags="grid")
        x_label = "Input effort" if self.human_labels.get() else "Input Speed"
        self.canvas.create_text(CANVAS_WIDTH/2, CANVAS_HEIGHT - MARGIN + 5,
                                text=x_label, font=("Arial", 12),
                                anchor="n", tags="grid")
        self.canvas.create_text(MARGIN - 5, CANVAS_HEIGHT/2,
                                text="Output Speed", font=("Arial", 12),
                                anchor="e", angle=90, tags="grid")

    def update_curve_from_options(self):
        self.selected_indices.clear()
        if self.use_windows_curve.get():
            self.points = [pt.copy() for pt in WINDOWS_CURVE]
        else:
            low = [0.0, 0.0]
            mid = [0.5, 1.5] if self.enable_nonlinear_boost.get() else [0.5, 0.5]
            high = [1.0, 2.5] if self.enable_acceleration_cap.get() else [1.0, 1.0]
            self.points = [low, mid, high]
        self.draw_curve()

    def increase_all_points(self):
        for i in self.selected_indices:
            if i == 0 and self.lock_low_speed.get():
                continue
            self.points[i][1] = min(Y_MAX, self.points[i][1] + DELTA_Y)
        self.draw_curve()

    def decrease_all_points(self):
        for i in self.selected_indices:
            if i == 0 and self.lock_low_speed.get():
                continue
            self.points[i][1] = max(Y_MIN, self.points[i][1] - DELTA_Y)
        self.draw_curve()

    def draw_curve(self):
        self.canvas.delete("curve")
        for i in range(len(self.points) - 1):
            x1, y1 = to_canvas_coords(*self.points[i])
            x2, y2 = to_canvas_coords(*self.points[i + 1])
            self.canvas.create_line(x1, y1, x2, y2, fill="blue", width=2, tags="curve")
        for idx, (x, y) in enumerate(self.points):
            cx, cy = to_canvas_coords(x, y)
            if idx in self.selected_indices:
                outline_color = "green"
                outline_width = 3
            else:
                outline_color = "black"
                outline_width = 1
            self.canvas.create_oval(cx - POINT_RADIUS, cy - POINT_RADIUS,
                                    cx + POINT_RADIUS, cy + POINT_RADIUS,
                                    fill="red", outline=outline_color, width=outline_width,
                                    tags=("curve", f"pt{idx}"))
        self.update_values_label()
        self.auto_apply_xinput()

    def update_values_label(self):
        if len(self.points) == 3:
            names = ["Low speed (min)", "Mid speed", "High speed (max)"]
        elif len(self.points) == 4:
            names = ["Low speed (min)", "Early accel", "Advanced accel", "High speed (max)"]
        else:
            names = [f"Point {i}" for i in range(len(self.points))]
        values_text = "Control Points:\n" + "\n".join(
            f"{name}: (Input: {x:.2f}, Output: {y:.2f})"
            for name, (x, y) in zip(names, self.points)
        )
        self.values_label.config(text=values_text)

    def auto_apply_xinput(self):
        if platform.system() != "Linux":
            return
        device_name = self.device_name_var.get()
        y_values = [f"{pt[1]:.2f}" for pt in self.points]
        try:
            props = subprocess.run(
                ["xinput", "list-props", device_name],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            ).stdout
            if "libinput Accel Custom Motion Points" not in props or "libinput Accel Profile Enabled" not in props:
                print("Error: The required properties are not supported by the device.")
                return
            subprocess.run(
                ["xinput", "set-prop", device_name, "libinput Accel Custom Motion Points"] + y_values,
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["xinput", "set-prop", device_name, "libinput Accel Custom Motion Step", "1.0"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["xinput", "set-prop", device_name, "libinput Accel Profile Enabled", "0", "0", "1"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError as e:
            print(f"Error: Could not apply xinput settings. {e}")

    def find_nearby_point(self, x, y):
        for idx, (pt_x, pt_y) in enumerate(self.points):
            cx, cy = to_canvas_coords(pt_x, pt_y)
            if (cx - x) ** 2 + (cy - y) ** 2 <= POINT_RADIUS ** 2:
                return idx
        return None

    def on_press(self, event):
        idx = self.find_nearby_point(event.x, event.y)
        shift_pressed = bool(event.state & 0x0001)
        # If the low speed control point is locked, ignore clicks on it.
        if idx == 0 and self.lock_low_speed.get():
            return
        if idx is not None:
            if shift_pressed:
                if idx in self.selected_indices:
                    self.selected_indices.remove(idx)
                else:
                    self.selected_indices.add(idx)
            else:
                self.selected_indices = {idx}
            self.drag_data["point_index"] = idx
            cx, cy = to_canvas_coords(*self.points[idx])
            self.drag_data["offset_x"] = cx - event.x
            self.drag_data["offset_y"] = cy - event.y
        else:
            self.selected_indices.clear()
        self.draw_curve()

    def on_drag(self, event):
        idx = self.drag_data["point_index"]
        if idx is None:
            return
        # In case the locked point was somehow selected, do not drag it.
        if idx == 0 and self.lock_low_speed.get():
            return
        new_cx = event.x + self.drag_data["offset_x"]
        new_cy = event.y + self.drag_data["offset_y"]
        new_x, new_y = to_function_coords(new_cx, new_cy)
        new_x = max(X_MIN, min(X_MAX, new_x))
        new_y = max(Y_MIN, min(Y_MAX, new_y))
        if idx > 0 and new_x < self.points[idx - 1][0]:
            new_x = self.points[idx - 1][0]
        if idx < len(self.points) - 1 and new_x > self.points[idx + 1][0]:
            new_x = self.points[idx + 1][0]
        self.points[idx] = [new_x, new_y]
        self.draw_curve()

    def on_release(self, event):
        self.drag_data["point_index"] = None

if __name__ == "__main__":
    app = CurveEditor()
    app.mainloop()
