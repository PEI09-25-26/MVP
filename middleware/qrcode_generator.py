import qrcode
import cv2
import numpy as np

def generate_qr_code(data):
    pil_img = qrcode.make(data).convert("RGB")
    open_cv_image = np.array(pil_img)
    open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)

    cv2.imshow("Link Qr Code", open_cv_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()