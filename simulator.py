#!/usr/bin/env python3
import tkinter as tk
import subprocess
import platform

# Canvas dimensions and coordinate ranges
CANVAS_WIDTH = 500
CANVAS_HEIGHT = 500
X_MIN, X_MAX = 0.0, 1.0   # Normalized input speed range
Y_MIN, Y_MAX = 0.0, 3.0   # Normalized output speed range (extended for boost/cap)
POINT_RADIUS = 6

# Device name for xinput. Update this to match your device.
DEVICE_NAME = "YOUR_DEVICE_NAME_HERE"

# Predefined Windows-like preset (4 points)
WINDOWS_CURVE = [
    [0.0, 0.0],   # Low speed (min)
    [0.3, 0.3],   # Early acceleration start
    [0.6, 1.2],   # Advanced acceleration
    [1.0, 2.5],   # High speed cap
]

def to_canvas_coords(x, y):
    """Map (x, y) in [X_MIN,X_MAX]x[Y_MIN,Y_MAX] to canvas pixel coordinates."""
    canvas_x = (x - X_MIN) / (X_MAX - X_MIN) * CANVAS_WIDTH
    canvas_y = CANVAS_HEIGHT - (y - Y_MIN) / (Y_MAX - Y_MIN) * CANVAS_HEIGHT
    return canvas_x, canvas_y

def to_function_coords(canvas_x, canvas_y):
    """Map canvas pixel coordinates back to function coordinates."""
    x = canvas_x / CANVAS_WIDTH * (X_MAX - X_MIN) + X_MIN
    y = (CANVAS_HEIGHT - canvas_y) / CANVAS_HEIGHT * (Y_MAX - Y_MIN) + Y_MIN
    return x, y

class CurveEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Custom Pointer Acceleration Curve Editor")

        # Create variables for each checkbox
        self.use_windows_curve = tk.BooleanVar(value=False)
        self.enable_nonlinear_boost = tk.BooleanVar(value=False)
        self.enable_acceleration_cap = tk.BooleanVar(value=False)

        # Frame for options
        options_frame = tk.Frame(self)
        options_frame.pack(pady=5)

        # Windows-like curve checkbox
        self.win_chk = tk.Checkbutton(
            options_frame, text="Use Windows-like curve",
            variable=self.use_windows_curve, command=self.update_curve_from_options
        )
        self.win_chk.grid(row=0, column=0, sticky="w")

        # Non-linear boost checkbox
        self.boost_chk = tk.Checkbutton(
            options_frame, text="Enable Non-linear Boost",
            variable=self.enable_nonlinear_boost, command=self.update_curve_from_options
        )
        self.boost_chk.grid(row=0, column=1, sticky="w")

        # Acceleration cap checkbox
        self.cap_chk = tk.Checkbutton(
            options_frame, text="Enable Acceleration Cap",
            variable=self.enable_acceleration_cap, command=self.update_curve_from_options
        )
        self.cap_chk.grid(row=0, column=2, sticky="w")

        self.canvas = tk.Canvas(self, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="white")
        self.canvas.pack(fill="both", expand=True)

        # Label to display control point values
        self.values_label = tk.Label(self, text="", font=("Arial", 10))
        self.values_label.pack(pady=5)

        # Explanatory notes
        explanation = (
            "Instructions:\n"
            "Toggle the options above to test various findings from reverse-engineering Windows pointer acceleration:\n"
            " • **Use Windows-like curve:** Loads a preset approximating Windows’ S-curve behavior.\n"
            " • **Enable Non-linear Boost:** Raises the mid-speed point to simulate enhanced acceleration in the mid-range.\n"
            " • **Enable Acceleration Cap:** Increases the output at high speeds (a cap) instead of a linear mapping.\n\n"
            "When options are changed, the curve is recalculated and auto-applied via xinput (Linux only).\n"
            "You can then adjust control points interactively."
        )
        self.explanation_label = tk.Label(self, text=explanation, font=("Arial", 9),
                                          justify="left", wraplength=CANVAS_WIDTH)
        self.explanation_label.pack(pady=5)

        # Start with a default curve (we'll use a simple 3-point curve as the baseline)
        self.points = [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
        self.drag_data = {"point_index": None, "offset_x": 0, "offset_y": 0}

        self.draw_grid()
        self.update_curve_from_options()  # Update curve based on initial checkbox states

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def update_curve_from_options(self):
        """Update the control points based on the current checkbox settings."""
        if self.use_windows_curve.get():
            # Use the Windows-like preset (ignore other options)
            self.points = [pt.copy() for pt in WINDOWS_CURVE]
        else:
            # Build a base 3-point curve: low and high remain fixed; mid varies based on toggles.
            low = [0.0, 0.0]
            # Base mid point is at half input; default output is linear.
            if self.enable_nonlinear_boost.get():
                # Raise the mid output for a non-linear boost.
                mid = [0.5, 1.5]
            else:
                mid = [0.5, 0.5]
            if self.enable_acceleration_cap.get():
                high = [1.0, 2.5]
            else:
                high = [1.0, 1.0]
            self.points = [low, mid, high]
        self.draw_curve()

    def draw_grid(self):
        for i in range(11):
            x = i / 10 * CANVAS_WIDTH
            self.canvas.create_line(x, 0, x, CANVAS_HEIGHT, fill="#ddd")
            y = i / 10 * CANVAS_HEIGHT
            self.canvas.create_line(0, y, CANVAS_WIDTH, y, fill="#ddd")

    def draw_curve(self):
        self.canvas.delete("curve")
        # Draw line segments between control points
        for i in range(len(self.points) - 1):
            x1, y1 = to_canvas_coords(*self.points[i])
            x2, y2 = to_canvas_coords(*self.points[i + 1])
            self.canvas.create_line(x1, y1, x2, y2, fill="blue", width=2, tags="curve")
        # Draw control points as red circles
        for idx, (x, y) in enumerate(self.points):
            cx, cy = to_canvas_coords(x, y)
            self.canvas.create_oval(cx - POINT_RADIUS, cy - POINT_RADIUS,
                                    cx + POINT_RADIUS, cy + POINT_RADIUS,
                                    fill="red", outline="black", tags=("curve", f"pt{idx}"))
        self.update_values_label()
        self.auto_apply_xinput()

    def update_values_label(self):
        # Dynamically name the points based on the number of points
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
        """Auto-apply the custom curve via xinput only if running on Linux."""
        if platform.system() != "Linux":
            return
        y_values = [f"{pt[1]:.2f}" for pt in self.points]
        try:
            subprocess.run(
                ["xinput", "set-prop", DEVICE_NAME, "libinput Accel Custom Motion Points"] + y_values,
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["xinput", "set-prop", DEVICE_NAME, "libinput Accel Custom Motion Points", "1.0"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["xinput", "set-prop", DEVICE_NAME, "libinput Accel Profile Enabled", "0", "0", "1"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            print("Error: Could not apply xinput settings. Check your device name and property support.")

    def find_nearby_point(self, x, y):
        for idx, (pt_x, pt_y) in enumerate(self.points):
            cx, cy = to_canvas_coords(pt_x, pt_y)
            if (cx - x) ** 2 + (cy - y) ** 2 <= POINT_RADIUS ** 2:
                return idx
        return None

    def on_press(self, event):
        idx = self.find_nearby_point(event.x, event.y)
        if idx is not None:
            self.drag_data["point_index"] = idx
            cx, cy = to_canvas_coords(*self.points[idx])
            self.drag_data["offset_x"] = cx - event.x
            self.drag_data["offset_y"] = cy - event.y

    def on_drag(self, event):
        idx = self.drag_data["point_index"]
        if idx is None:
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
