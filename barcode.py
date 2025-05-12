import cv2
from pyzbar.pyzbar import decode

def capture_and_decode_barcode():
    # Initialize webcam video capture
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("Error: Could not open video source.")
        return

    # Capture a single frame
    ret, frame = cap.read()
    if not ret:
        print("Error: Couldn't grab frame.")
        return

    # Convert frame to grayscale for barcode detection
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect barcodes in the grayscale image
    barcodes = decode(gray)

    if barcodes:
        # Loop over detected barcodes
        for barcode in barcodes:
            # Extract barcode data and type
            barcode_data = barcode.data.decode("utf-8")
            barcode_type = barcode.type

            # Check if it is a Code 39 barcode
            if barcode_type == "CODE39":
                print(f"Code 39 Barcode Detected: {barcode_data}")
            else:
                print(f"Barcode Data: {barcode_data}")
                print(f"Barcode Type: {barcode_type}")

            # Draw a rectangle around the barcode
            (x, y, w, h) = barcode.rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

            # Put barcode data and type on the image
            cv2.putText(frame, f"{barcode_data} ({barcode_type})",
                        (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # Display the resulting frame with the barcode
        cv2.imshow('Captured Image with Barcode', frame)
    else:
        print("No barcode detected.")
        cv2.imshow('Captured Image', frame)

    # Wait for a key press to close the window
    cv2.waitKey(0)

    # Release the camera and close windows
    cap.release()
    cv2.destroyAllWindows()

# Run the function
capture_and_decode_barcode()
