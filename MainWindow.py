import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea, QLabel, QPushButton, QFileDialog, QTextEdit, QDialog, QMessageBox
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt
import pytesseract
from pdf2image import convert_from_path
from lxml import etree
from transliterate import translit

class PdfViewer(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignTop)
        self.setWidget(self.image_label)

    def set_image(self, pixmap):
        self.image_label.setPixmap(pixmap)

#edit
class EditWindow(QDialog):
    def __init__(self, word_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Transliterated Text")
        self.setGeometry(100, 100, 600, 400)

        self.word_data = word_data
        self.parent = parent

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(' '.join([word['latin'] for word in self.word_data]))
        layout.addWidget(self.text_edit)

        self.save_button = QPushButton("Save Changes")
        self.save_button.clicked.connect(self.save_changes)
        layout.addWidget(self.save_button)

    def save_changes(self):
        new_text = self.text_edit.toPlainText()
        new_words = new_text.split()

        if len(new_words) != len(self.word_data):
            QMessageBox.warning(self, "Error", "The number of words must remain the same.")
            return

        for i, word in enumerate(self.word_data):
            word['latin'] = new_words[i]

        self.parent.redraw_pdf()
        self.close()

class UploadWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Upload file")
        self.setGeometry(100, 100, 400, 200)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        #file picker button
        self.file_dialog_button = QPushButton("Select PDF", self)
        self.file_dialog_button.clicked.connect(self.open_file_dialog)
        layout.addWidget(self.file_dialog_button)

        #file label
        self.file_label = QLabel("No file selected", self)
        self.file_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.file_label)

        #upload button
        self.upload_button = QPushButton("Upload", self)
        self.upload_button.clicked.connect(self.move_to_main_window)
        self.upload_button.setEnabled(False)
        layout.addWidget(self.upload_button)

        self.selected_file_path = None

    def open_file_dialog(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Select PDF File", "", "PDF Files (*.pdf)", options=options)
        if file_name:
            self.selected_file_path = file_name
            self.file_label.setText(f"Selected file: {file_name}")
            self.upload_button.setEnabled(True)

    def move_to_main_window(self):
        if self.selected_file_path:
            self.main_window = MainWindow()
            self.main_window.load_pdf(
                self.selected_file_path
            )
            self.main_window.show()
            self.close()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF View")
        self.setGeometry(100, 100, 1200, 800)

        self.word_data = []
        self.original_images = []
        self.modified_images = []
        self.current_highlights = []
        self.scale_factor = 75 / 300 #resize the pdf views

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        #search bar and edit button
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setAlignment(Qt.AlignCenter)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setFixedWidth(80)
        self.edit_button.clicked.connect(self.open_edit_window)
        search_layout.addWidget(self.edit_button)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.setFixedWidth(400)
        self.search_bar.textChanged.connect(self.highlight_matches)
        search_layout.addWidget(self.search_bar)

        #clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.setFixedWidth(80)
        self.clear_button.clicked.connect(self.clear_search_box)
        search_layout.addWidget(self.clear_button)
        layout.addWidget(search_container)

        # PDF viewers
        viewer_layout = QHBoxLayout()
        self.original_viewer = PdfViewer()
        self.modified_viewer = PdfViewer()
        viewer_layout.addWidget(self.original_viewer)
        viewer_layout.addWidget(self.modified_viewer)
        layout.addLayout(viewer_layout)

    def open_edit_window(self):
        self.edit_window = EditWindow(self.word_data, self)
        self.edit_window.show()

    def redraw_pdf(self):
        self.modified_images = []
        for page_num, image in enumerate(self.original_images):
            high_res_image = image.resize(
                (int(image.width / self.scale_factor), int(image.height / self.scale_factor)),
                Image.Resampling.LANCZOS
            )
            draw = ImageDraw.Draw(high_res_image)

            for word in [word for word in self.word_data if word['page'] == page_num]:
                bbox = word['bbox']
                latin_word = word['latin']

                font_size = 50
                font = ImageFont.truetype('/Library/Fonts/Arial Unicode.ttf', int(font_size))

                text_bbox = draw.textbbox((0, 0), latin_word, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                #calculate the center position for the text
                bbox_width = bbox[2] - bbox[0]
                bbox_height = bbox[3] - bbox[1]
                x_center = bbox[0] + (bbox_width - text_width) / 2
                y_center = bbox[1] + (bbox_height - text_height) / 2

                draw.rectangle(bbox, fill='white')
                draw.text((x_center, y_center), latin_word, fill='black', font=font)

            resized_modified_image = high_res_image.resize(
                (int(high_res_image.width * self.scale_factor), int(high_res_image.height * self.scale_factor)),
                Image.Resampling.LANCZOS
            )
            self.modified_images.append(resized_modified_image)

        self.show_images()

    def clear_search_box(self):
        self.search_bar.clear()
        self.show_images()

    def load_pdf(self, pdf_path):
        poppler_path = "/opt/miniconda3/bin"  #poppler coda PATH

        """
        the actual value of the document dpi can influence on how the pdf itself is rendered later. 
        Sometimes there is a shearing effect that can happen with some pdf that it doesn't like for some reason
        
        standard value is 300 but 400 can also work for some files.
        """

        self.original_images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)

        self.word_data = []
        self.modified_images = []

        for page_num, image in enumerate(self.original_images):
            hocr_data = pytesseract.image_to_pdf_or_hocr(image, extension='hocr', lang='eng+rus')

            with open(f'page_{page_num + 1}_hocr.xml', 'wb') as hf:
                hf.write(hocr_data)

            root = etree.fromstring(hocr_data)
            page_boxes = self.parse_hocr(root)

            #modified image
            modified_image = image.copy()
            draw = ImageDraw.Draw(modified_image)

            for bbox, cyrillic_word in page_boxes:
                latin_word = translit(cyrillic_word, 'ru', reversed=True)

                # Store word data
                self.word_data.append({
                    'cyrillic': cyrillic_word,
                    'latin': latin_word,
                    'bbox': bbox,  # bbox is still in 300 DPI coordinates
                    'page': page_num
                })

                # Calculate font size based on bounding box height
                font_size = 50
                font = ImageFont.truetype('/Library/Fonts/Arial Unicode.ttf', int(font_size))

                # Calculate the text bounding box
                text_bbox = draw.textbbox((0, 0), latin_word, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                # Calculate the center position for the text
                bbox_width = bbox[2] - bbox[0]
                bbox_height = bbox[3] - bbox[1]
                x_center = bbox[0] + (bbox_width - text_width) / 2
                y_center = bbox[1] + (bbox_height - text_height) / 2

                #blank out text
                draw.rectangle(bbox, fill='white')
                draw.text((x_center, y_center), latin_word, fill='black', font=font)

            #resize
            resized_modified_image = modified_image.resize(
                (int(modified_image.width * self.scale_factor), int(modified_image.height * self.scale_factor)),
                Image.Resampling.LANCZOS
            )
            self.modified_images.append(resized_modified_image)

            #zoom out image
            resized_original_image = image.resize(
                (int(image.width * self.scale_factor), int(image.height * self.scale_factor)),
                Image.Resampling.LANCZOS
            )
            self.original_images[page_num] = resized_original_image

            with open(f'page_{page_num + 1}_cyrillic.txt', 'w', encoding='utf-8') as f:
                f.write(' '.join([word['cyrillic'] for word in self.word_data if word['page'] == page_num]))
            with open(f'page_{page_num + 1}_latin.txt', 'w', encoding='utf-8') as f:
                f.write(' '.join([word['latin'] for word in self.word_data if word['page'] == page_num]))

        self.show_images()

    def parse_hocr(self, root):
        word_boxes = []
        for elem in root.xpath('//*[@class="ocrx_word"]'):
            title = elem.get('title')
            conf = float(title.split(';')[1].split()[-1])
            if conf < 8:
                continue

            bbox = list(map(int, title.split(';')[0].split()[1:]))
            text = ''.join(elem.itertext()).strip()
            if text:
                if bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                    word_boxes.append((bbox, text))
        return word_boxes

    def show_images(self):
        # convert PIL images to qpixmaps
        original_pixmap = self.create_composite_pixmap(self.original_images)
        modified_pixmap = self.create_composite_pixmap(self.modified_images)

        self.original_viewer.set_image(original_pixmap)
        self.modified_viewer.set_image(modified_pixmap)

    def create_composite_pixmap(self, images):
        total_height = sum(img.height for img in images)
        max_width = max(img.width for img in images)
        composite = Image.new('RGB', (max_width, total_height), 'white')
        y_offset = 0
        for img in images:
            composite.paste(img, (0, y_offset))
            y_offset += img.height

        qimage = QImage(
            composite.tobytes(),
            composite.width,
            composite.height,
            QImage.Format_RGB888
        )
        return QPixmap.fromImage(qimage)

    def highlight_matches(self, text):
        if not text:
            self.show_images()
            return

        matches = [wd for wd in self.word_data
                   if text.lower() in wd['cyrillic'].lower() or
                   text.lower() in wd['latin'].lower()]

        #highlight
        orig_highlighted = self.highlight_images(self.original_images, matches)
        mod_highlighted = self.highlight_images(self.modified_images, matches)

        self.original_viewer.set_image(self.create_composite_pixmap(orig_highlighted))
        self.modified_viewer.set_image(self.create_composite_pixmap(mod_highlighted))

    def highlight_images(self, base_images, matches):
        highlighted_images = []
        for page_num, img in enumerate(base_images):
            page_img = img.copy()
            draw = ImageDraw.Draw(page_img)

            for match in [m for m in matches if m['page'] == page_num]:
                scaled_bbox = [
                    int(match['bbox'][0] * self.scale_factor),
                    int(match['bbox'][1] * self.scale_factor),
                    int(match['bbox'][2] * self.scale_factor),
                    int(match['bbox'][3] * self.scale_factor)
                ]
                draw.rectangle(scaled_bbox, outline='blue', width=1)

            highlighted_images.append(page_img)
        return highlighted_images

if __name__ == "__main__":
    app = QApplication(sys.argv)

    upload_window = UploadWindow()
    upload_window.show()

    sys.exit(app.exec())