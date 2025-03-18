import tkinter as tk
from tkinter import Canvas

def draw_graph(points):
    root = tk.Tk()
    root.title("Mouse Curve Graph")
    canvas = Canvas(root, width=500, height=500, bg="white")
    canvas.pack()
    
    scale_x = 10
    scale_y = 10
    offset_x = 50
    offset_y = 450
    
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        canvas.create_line(
            offset_x + x1 * scale_x, offset_y - y1 * scale_y,
            offset_x + x2 * scale_x, offset_y - y2 * scale_y,
            fill="blue", width=2
        )
        canvas.create_text(
            offset_x + x1 * scale_x, offset_y - y1 * scale_y,
            text=f"({x1:.2f}, {y1:.2f})", anchor=tk.SE, fill="black"
        )
    
    x_last, y_last = points[-1]
    canvas.create_text(
        offset_x + x_last * scale_x, offset_y - y_last * scale_y,
        text=f"({x_last:.2f}, {y_last:.2f})", anchor=tk.SE, fill="black"
    )
    
    root.mainloop()

def hex_to_decimal(hex_values):
    points = []
    for i in range(0, len(hex_values), 8):
        hex_chunk = hex_values[i:i+8]
        integer_part = int.from_bytes(hex_chunk[2:4], byteorder='little', signed=True)
        fractional_part = int.from_bytes(hex_chunk[0:2], byteorder='little', signed=False) / 65536.0
        decimal_value = integer_part + fractional_part
        points.append(decimal_value)
    return points

smooth_mouse_x_curve = [
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x15, 0x6e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x40, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x29, 0xdc, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00
]

smooth_mouse_y_curve = [
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0xfd, 0x11, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x24, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0xfc, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00,
    0xc0, 0xbb, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00
]

x_points = hex_to_decimal(smooth_mouse_x_curve)
y_points = hex_to_decimal(smooth_mouse_y_curve)

coordinates = list(zip(x_points, y_points))
draw_graph(coordinates)