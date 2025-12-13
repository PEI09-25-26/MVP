import cv2
import numpy as np

class CardDetector:
    """
    Detector Final v5: Garante geometria perfeita (Zero Skew/Distorção).
    Estratégia: Recorta a forma natural (seja landscape ou portrait) e 
    roda apenas no final.
    """
    
    def __init__(self, debug=True, min_area=5000, max_cards=10):
        self.debug = debug
        self.min_area = min_area
        self.max_cards = max_cards
        # Dimensões finais para o YOLO (Sempre Portrait/Em pé)
        self.card_width = 200
        self.card_height = 280

    def get_thresh(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blur, 255, 
                                     cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY_INV, 11, 2)
        kernel = np.ones((3, 3), np.uint8)
        thresh = cv2.erode(thresh, kernel, iterations=1)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        return thresh

    def reorder_points_circular(self, pts):
        """
        Ordena os pontos [TL, TR, BR, BL] de forma circular.
        Essencial para evitar que a imagem fique 'baralhada'.
        """
        pts = pts.reshape(4, 2)
        center = np.mean(pts, axis=0)
        angles = np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0])
        sort_indices = np.argsort(angles)
        sorted_pts = pts[sort_indices]
        
        # Encontrar o ponto Top-Left (menor soma x+y) para ser o primeiro
        s = sorted_pts.sum(axis=1)
        tl_idx = np.argmin(s)
        ordered = np.roll(sorted_pts, -tl_idx, axis=0)
        
        return ordered.astype("float32")

    def find_corners_set(self, img, original, draw=False):
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        proper = sorted(contours, key=cv2.contourArea, reverse=True)[:self.max_cards * 2]
        four_corners_set = []

        for cnt in proper:
            area = cv2.contourArea(cnt)
            if area > self.min_area:
                # Usa minAreaRect para pegar a caixa rodada real
                rect = cv2.minAreaRect(cnt)
                (w_real, h_real) = rect[1]
                
                if w_real == 0 or h_real == 0: continue

                # Filtro de geometria básica
                ar = w_real / float(h_real)
                check_ar = ar if ar >= 1 else 1/ar
                
                if 1.1 <= check_ar <= 2.5:
                    box = cv2.boxPoints(rect)
                    box = np.int64(box) # Correção para o erro do numpy
                    
                    if draw:
                        cv2.drawContours(original, [box], 0, (0, 255, 0), 2)

                    pts = box.reshape(4, 2)
                    ordered_pts = self.reorder_points_circular(pts)
                    four_corners_set.append(ordered_pts.reshape(4, 1, 2))

        return four_corners_set

    def find_flatten_cards(self, img, set_of_corners):
        img_outputs = []
        
        for corners in set_of_corners:
            pts = corners.reshape(4, 2)
            
            # 1. Medir as dimensões VISUAIS deste contorno específico
            # Largura (Topo): Distância entre ponto 0 e 1
            width = np.linalg.norm(pts[0] - pts[1])
            # Altura (Lado): Distância entre ponto 1 e 2
            height = np.linalg.norm(pts[1] - pts[2])

            # 2. Decisão Geométrica:
            # Se a largura visual for maior, o destino TEM de ser Landscape (largo).
            # Se a altura visual for maior, o destino TEM de ser Portrait (alto).
            
            if width > height:
                # Configurar destino como Landscape (280x200)
                # Isto "casa" perfeitamente com a carta deitada, sem distorção.
                dst_w = self.card_height  # 280
                dst_h = self.card_width   # 200
                needs_rotation = True     # Marcamos para rodar no fim
            else:
                # Configurar destino como Portrait (200x280)
                dst_w = self.card_width   # 200
                dst_h = self.card_height  # 280
                needs_rotation = False

            # Pontos de destino perfeitos (sempre começa no 0,0)
            pts2 = np.array([
                [0, 0],
                [dst_w - 1, 0],
                [dst_w - 1, dst_h - 1],
                [0, dst_h - 1]
            ], dtype="float32")

            # 3. Transformação de Perspetiva (Warp)
            matrix = cv2.getPerspectiveTransform(pts, pts2)
            img_output = cv2.warpPerspective(img, matrix, (dst_w, dst_h))

            # 4. Rotação Final
            # Se a carta estava deitada, agora que está recortada e limpa,
            # rodamo-la 90 graus para ficar em pé para o YOLO.
            if needs_rotation:
                img_output = cv2.rotate(img_output, cv2.ROTATE_90_CLOCKWISE)

            # 5. Garantia Final de Tamanho
            # Assegura que sai sempre 200x280, aconteça o que acontecer.
            img_output = cv2.resize(img_output, (self.card_width, self.card_height))
            
            img_outputs.append(img_output)

        return img_outputs

    def detect_cards_from_frame(self, frame):
        # Resize inicial para performance
        scale = 0.75
        h, w = frame.shape[:2]
        small_frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        
        debug_img = small_frame.copy() if self.debug else None

        thresh = self.get_thresh(small_frame)
        four_corners_set = self.find_corners_set(thresh, debug_img, draw=self.debug)
        
        # Passar o frame colorido para recorte
        flatten_cards = self.find_flatten_cards(small_frame, four_corners_set)

        if self.debug:
            debug_img = cv2.resize(debug_img, (w, h))
        else:
            debug_img = frame

        return flatten_cards, debug_img, four_corners_set