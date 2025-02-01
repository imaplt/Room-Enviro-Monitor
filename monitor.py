import time
import board
import busio
import digitalio
import adafruit_sht4x
from PIL import Image, ImageDraw, ImageFont
import datetime
import traceback
import collections
from adafruit_rgb_display import st7789

# Log files
LOG_FILE = "sensor_log.txt"
SNAPSHOT_FILE = "snapshots.txt"

# Initialize I2C and SHT4x sensor
i2c = busio.I2C(board.SCL, board.SDA)
try:
    sensor = adafruit_sht4x.SHT4x(i2c)
    sensor.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
except Exception as e:
    print(f"Error initializing SHT4x: {e}")
    traceback.print_exc()
    exit(1)

# Initialize ST7789 Display
cs_pin = digitalio.DigitalInOut(board.CE0)
dc_pin = digitalio.DigitalInOut(board.D25)
reset_pin = digitalio.DigitalInOut(board.D24)
backlight = digitalio.DigitalInOut(board.D26)
backlight.switch_to_output()
backlight.value = True  # Turn on backlight

BAUDRATE = 24000000
spi = board.SPI()

display = st7789.ST7789(
    spi,
    height=240,
    y_offset=80,
    rotation=180,
    cs=cs_pin,
    dc=dc_pin,
    rst=reset_pin,
    baudrate=BAUDRATE,
)

# Initialize Buttons
button_A = digitalio.DigitalInOut(board.D5)  # Show 15-min average
button_A.switch_to_input(pull=digitalio.Pull.UP)

button_B = digitalio.DigitalInOut(board.D6)  # Save snapshot
button_B.switch_to_input(pull=digitalio.Pull.UP)

# Create blank image for drawing
width, height = display.width, display.height
image = Image.new("RGB", (width, height), "black")
draw = ImageDraw.Draw(image)

# Load font
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
except IOError:
    font = ImageFont.load_default()

# Data storage
prev_temp = None
prev_humidity = None
history = collections.deque(maxlen=900)  # Stores 15 min of readings

def c_to_f(celsius):
    """Convert Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32

def log_change(temp_f, humidity):
    """Logs significant temperature and humidity changes."""
    with open(LOG_FILE, "a") as log:
        log.write(f"{datetime.datetime.now()} - Temp: {temp_f:.2f}°F, Humidity: {humidity:.2f}%\n")

def save_snapshot(temp_f, humidity):
    """Saves a snapshot of current readings to a file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(SNAPSHOT_FILE, "a") as snap:
        snap.write(f"{timestamp} - Temp: {temp_f:.2f}°F, Humidity: {humidity:.2f}%\n")

    # Display confirmation
    draw.rectangle((0, 0, width, height), fill="black")
    draw.text((30, 80), "Snapshot Saved!", font=font, fill="yellow")
    draw.text((30, 120), timestamp, font=font, fill="white")
    display.image(image)
    time.sleep(2)  # Show for 2 seconds

def draw_running_indicator(frame):
    """Draws a small animated progress bar to indicate the script is running."""
    bar_width = 50
    bar_x = width - bar_width - 10
    bar_y = height - 10
    progress = (frame % bar_width)  # Move animation frame
    draw.rectangle((bar_x, bar_y - 5, bar_x + progress, bar_y), fill="green")

def draw_graphical_display(temp_f, humidity, frame):
    """Draws graphical bars for temperature and humidity."""
    draw.rectangle((0, 0, width, height), fill="black")
    draw.text((20, 20), f"Temp: {temp_f:.1f}°F", font=font, fill="white")
    draw.text((20, 50), f"Humidity: {humidity:.1f}%", font=font, fill="white")

    # Temperature bar (scaled to 122°F max)
    temp_bar_height = int((temp_f / 122.0) * 150)
    draw.rectangle((180, 200 - temp_bar_height, 210, 200), fill="red")

    # Humidity bar (scaled to 100% max)
    hum_bar_height = int((humidity / 100.0) * 150)
    draw.rectangle((220, 200 - hum_bar_height, 250, 200), fill="blue")

    # Running animation
    draw_running_indicator(frame)

    display.image(image)

def draw_average_display():
    """Displays the 15-minute average in Fahrenheit."""
    if len(history) == 0:
        return  # No data available

    avg_temp_c = sum(t for t, _ in history) / len(history)
    avg_temp_f = c_to_f(avg_temp_c)
    avg_humidity = sum(h for _, h in history) / len(history)

    draw.rectangle((0, 0, width, height), fill="black")
    draw.text((40, 50), "15 Min Avg:", font=font, fill="yellow")
    draw.text((40, 100), f"Temp: {avg_temp_f:.1f}°F", font=font, fill="white")
    draw.text((40, 150), f"Humidity: {avg_humidity:.1f}%", font=font, fill="white")

    display.image(image)
    time.sleep(3)  # Show for 3 seconds

try:
    print("Starting sensor monitoring...")
    frame = 0  # Animation frame counter

    while True:
        try:
            # Read sensor data
            temperature_c, humidity = sensor.measurements
            temperature_f = c_to_f(temperature_c)

            print(f"Temp: {temperature_f:.2f}°F, Humidity: {humidity:.2f}%")

            # Store latest reading
            history.append((temperature_c, humidity))

            # Update graphical display
            draw_graphical_display(temperature_f, humidity, frame)
            frame += 2  # Move animation forward

            # Log changes
            if prev_temp is None or abs(temperature_f - prev_temp) > 0.3 or abs(humidity - prev_humidity) > 0.3:
                log_change(temperature_f, humidity)
                prev_temp, prev_humidity = temperature_f, humidity

            # Check for button presses
            if not button_A.value:
                print("Button A Pressed - Showing 15-Min Average")
                draw_average_display()

            if not button_B.value:
                print("Button B Pressed - Saving Snapshot")
                save_snapshot(temperature_f, humidity)

            time.sleep(1)  # Update every second

        except Exception as e:
            print(f"Error reading sensor: {e}")
            traceback.print_exc()
            time.sleep(2)

except KeyboardInterrupt:
    print("Exiting...")
