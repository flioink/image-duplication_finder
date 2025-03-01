import os
import shutil
import sys
from PIL import Image
import imagehash

# pyqt imports
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, \
     QFileDialog, QGroupBox, QRadioButton


class DuplicateImagesDetector(QWidget):
    def __init__(self):
        super().__init__()
        # set window name and geometry
        self.setWindowTitle("Duplicated Image Detector")
        self.resize(400, 300)

        self.source_folder = ""
        self.dest_folder = ""

        self.source_files = []
        self.img_hashes_dict = {}
        self.duplicates_found = False

        self.master_layout = QVBoxLayout()

        self.init_ui()


    def init_ui(self):

        # source layout
        self.set_source_layout = QHBoxLayout()
        self.set_source_layout.setObjectName("source_layout")
        self.source_label = QLabel("Select a source folder")
        self.source_button = QPushButton("Source")
        self.set_source_layout.addWidget(self.source_label)
        self.set_source_layout.addWidget(self.source_button)

        # source info
        self.source_info_layout = QHBoxLayout()
        self.source_info_label = QLabel("Not selected yet")
        self.source_info_label.setStyleSheet("color: yellow; font-weight: bold;")
        self.source_info_layout.addWidget(self.source_info_label)

        # destination layout
        self.set_dest_layout = QHBoxLayout()
        self.set_dest_layout.setObjectName("dest_layout")
        self.dest_label = QLabel("Select output folder")
        self.dest_button = QPushButton("Destination")
        self.set_dest_layout.addWidget(self.dest_label)
        self.set_dest_layout.addWidget(self.dest_button)

        # destination info
        self.dest_info_layout = QHBoxLayout()
        self.dest_info_label = QLabel("Not selected yet")
        self.dest_info_label.setStyleSheet("color: yellow; font-weight: bold;")
        self.dest_info_layout.addWidget(self.dest_info_label)

        # comparison method selection
        self.method_group = QGroupBox("Comparison Method") # group box for the radio buttons
        self.method_layout = QVBoxLayout()
        # radio buttons
        self.exact_match_radio = QRadioButton("Exact Match")
        self.hashing_radio = QRadioButton("Perceptual Hashing")
        self.histogram_radio = QRadioButton("Histogram Comparison")

        self.exact_match_radio.setChecked(True)  # Default selection
        self.method_group.setDisabled(True)

        self.method_layout.addWidget(self.exact_match_radio)
        self.method_layout.addWidget(self.hashing_radio)
        self.method_layout.addWidget(self.histogram_radio)

        self.method_group.setLayout(self.method_layout)

        # execute button
        self.execute_comparison_layout = QVBoxLayout()
        self.execute_comparison_button = QPushButton("Execute")
        self.execute_comparison_layout.addWidget(self.execute_comparison_button)

        # add to master layout
        self.master_layout.addLayout(self.set_source_layout)
        self.master_layout.addLayout(self.source_info_layout)
        self.master_layout.addLayout(self.set_dest_layout)
        self.master_layout.addLayout(self.dest_info_layout)
        # align master layout to top
        self.master_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.master_layout.addWidget(self.method_group)
        self.method_layout.addLayout(self.execute_comparison_layout)

        # add master layout to the window
        self.setLayout(self.master_layout)

        self.style()

        self.event_handler()


    def style(self):
        self.setStyleSheet("""
                            QLabel, QPushButton{
                                font-family: calibri;
                            }

                            QLabel{
                                font-size: 20px;
                                font-style: italic;
                            }                                           

                            QPushButton{
                                font-size: 18px;
                                font-weight: bold;
                            }                                            


                            """)

    def event_handler(self):
        self.source_button.clicked.connect(self.open_source_dir)
        self.dest_button.clicked.connect(self.open_dest_dir)
        self.execute_comparison_button.clicked.connect(self.execute_search)

    def open_source_dir(self):

        path = QFileDialog.getExistingDirectory(self, "Select Folder")

        if not (os.path.exists(path) and os.path.isdir(path)):
            print("Invalid source folder.")
            return

        self.source_folder = path



        self.source_info_label.setText(f"Source: {self.source_folder}")
        self.source_info_label.setStyleSheet("color: green; font-weight: bold;")
        self.set_method_group_status()
        print(self.source_folder)


    def open_dest_dir(self):

        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not (os.path.exists(path) and os.path.isdir(path)):
            print("Invalid destination folder.")
            return

        self.dest_folder = path

        self.dest_info_label.setText(f"Destination: {self.dest_folder}")
        self.dest_info_label.setStyleSheet("color: green; font-weight: bold;")

        self.set_method_group_status()
        print(self.dest_folder)


    def set_method_group_status(self):
        if self.source_folder and self.dest_folder:
            self.method_group.setEnabled(True)
            self.load_file_paths()
        else:
            self.method_group.setEnabled(False)

    def load_file_paths(self):

        self.source_files.clear()  # Clear list before adding new entries

        files = [f for f in os.listdir(self.source_folder) if os.path.isfile(os.path.join(self.source_folder, f))]


        for file in files:
            if file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff")):
                self.source_files.append(os.path.join(self.source_folder, file))


    def execute_search(self):
        self.load_file_paths()
        self.exact_match_hashing()
        self.find_duplicates()



    def exact_match_hashing(self):
        self.img_hashes_dict.clear()
        self.duplicates_found = False
        # convert images to hashes and store in list
        if not self.source_files:
            print("No images found. Please select a valid folder.")
            return  # Exit early if there's nothing to process

        for file in self.source_files:
            with Image.open(file) as img:
                img_hash = str(imagehash.average_hash(img))

            # sets default value to a key - a list in this case and then updates value if key is found again
            self.img_hashes_dict.setdefault(img_hash, []).append(file)


    def find_duplicates(self):
        if not (os.path.exists(self.dest_folder) and os.path.isdir(self.dest_folder)):
            print("Invalid destination folder.")
            return

        self.move_duplicates()


    def move_duplicates(self):
        if self.dest_folder == self.source_folder:
            print("Warning! Destination folder not found!")
            return

        moved_files = []

        for hash_value, files in self.img_hashes_dict.items():
            if len(files) > 1:
                self.duplicates_found = True
                for f in files:
                    if not os.path.commonpath([f, self.dest_folder]) == self.dest_folder:
                        shutil.move(f, self.dest_folder)
                        moved_files.append(f)



        if not self.duplicates_found:
            print("No duplicates found.")

        else:
            print(f"Moved the following files: {moved_files}")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    detector = DuplicateImagesDetector()
    detector.show()
    sys.exit(app.exec())