import os
import shutil
import sys
import hashlib
import traceback
from multiprocessing.pool import worker

from PIL import Image
import imagehash

# pyqt imports
from PyQt6.QtCore import Qt, QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, \
    QFileDialog, QGroupBox, QRadioButton, QProgressBar


class WorkerSignals(QObject):

    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(float)

class Worker(QRunnable):

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        # Add the callback to our kwargs
        # self.kwargs["progress_callback"] = self.signals.progress

    @pyqtSlot()
    def run(self):
        try:
            if "progress_callback" in self.kwargs:
                result = self.fn(*self.args, progress_callback=self.kwargs["progress_callback"])
            else:
                result = self.fn(*self.args)
            self.signals.finished.emit()
        except Exception as e:
            print(f"Worker crashed: {e}")


class DuplicateImagesDetector(QWidget):
    def __init__(self):
        super().__init__()
        # set window name and geometry
        self.setWindowTitle("Duplicated Image Detector")
        self.resize(400, 300)
        self.selected_method = "Exact Match"

        self.source_folder = ""
        self.dest_folder = ""

        self.source_files = []
        self.img_hashes_dict = {}
        self.duplicates_found = False

        self.master_layout = QVBoxLayout()

        self.init_ui()
        self.threadpool = QThreadPool()


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
        self.exact_match_radio = QRadioButton("Exact Match - for finding exact copies. Fast")
        self.hashing_radio = QRadioButton("Perceptual Hashing - for same or similar images. Slower")
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

        # feedback layout
        self.feedback_layout = QVBoxLayout()
        self.feedback_info_label = QLabel()
        self.feedback_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setValue(0)
        self.feedback_layout.addWidget(self.feedback_info_label)
        self.feedback_layout.addWidget(self.progress_bar)



        # add to master layout
        self.master_layout.addLayout(self.set_source_layout)
        self.master_layout.addLayout(self.source_info_layout)
        self.master_layout.addLayout(self.set_dest_layout)
        self.master_layout.addLayout(self.dest_info_layout)
        # align master layout to top
        self.master_layout.addWidget(self.method_group)

        # add execute button to group layout
        self.method_layout.addLayout(self.execute_comparison_layout)

        # add the feedback layout
        self.master_layout.addLayout(self.feedback_layout)

        # add master layout to the window
        self.setLayout(self.master_layout)

        self.master_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

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
        # connect radio buttons
        self.exact_match_radio.toggled.connect(self.update_method)
        self.hashing_radio.toggled.connect(self.update_method)
        self.histogram_radio.toggled.connect(self.update_method)


    def update_method(self):
        if self.exact_match_radio.isChecked():
            self.selected_method = "Exact Match"
        elif self.hashing_radio.isChecked():
            self.selected_method = "Perceptual Hashing"
        elif self.histogram_radio.isChecked():
            self.selected_method = "Histogram Comparison"

        # print(f"Selected method: {self.selected_method}")


    def open_source_dir(self):

        path = QFileDialog.getExistingDirectory(self, "Select Folder")

        if not (os.path.exists(path) and os.path.isdir(path)):
            self.source_info_label.setText("Invalid source folder.")
            self.source_info_label.setStyleSheet("color: red; font-weight: bold;")
            print("Invalid source folder.")
            return

        self.source_folder = path
        self.feedback_info_label.clear()


        self.source_info_label.setText(f"Source: {self.source_folder}")
        self.source_info_label.setStyleSheet("color: green; font-weight: bold;")
        self.set_method_group_status()
        print(self.source_folder)


    def open_dest_dir(self):

        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not (os.path.exists(path) and os.path.isdir(path)):
            self.source_info_label.setText("Invalid destination folder.")
            self.source_info_label.setStyleSheet("color: red; font-weight: bold;")
            print("Invalid destination folder.")
            return

        self.dest_folder = path
        self.feedback_info_label.clear()

        self.dest_info_label.setText(f"Destination: {self.dest_folder}")
        self.dest_info_label.setStyleSheet("color: green; font-weight: bold;")

        self.set_method_group_status()
        print(self.dest_folder)


    def set_method_group_status(self):
        if self.source_folder and self.dest_folder:
            if  os.path.isdir(self.source_folder) and os.path.isdir(self.dest_folder):
                self.method_group.setEnabled(True)

        else:
            self.method_group.setEnabled(False)

    def load_file_paths(self):
        print("loading file paths")
        self.source_files.clear()  # Clear list before adding new entries

        files = [f for f in os.listdir(self.source_folder) if os.path.isfile(os.path.join(self.source_folder, f))]


        for file in files:
            if file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff")):
                self.source_files.append(os.path.join(self.source_folder, file))

    # execute button
    # Execute button
    def execute_search(self):

        if (os.path.isdir(self.source_folder) and os.path.isdir(self.dest_folder)) and \
                self.dest_folder != self.source_folder:

            self.load_file_paths()

            if not self.source_files:
                print("No files found! Exiting execution.")
                self.feedback_info_label.setText("No images found in the source folder.")
                return

            match self.selected_method:
                case "Exact Match":
                    print("Starting Exact Match Hashing")  # Debugging print
                    worker = Worker(self.exact_match_hashing)
                case "Perceptual Hashing":
                    print("Starting Perceptual Hashing")  # Debugging print
                    worker = Worker(self.perceptual_hashing)
                case "Histogram Comparison":
                    print("Starting Histogram Comparison")  # Debugging print
                    worker = Worker(self.histogram_comparison)
                    
                case _:
                    print("Error: No valid method selected!")  # Debugging print
                    self.feedback_info_label.setText("Invalid comparison method selected.")
                    return

            worker.signals.progress.connect(self.update_progress_bar)
            worker.signals.finished.connect(self.find_duplicates)

            print("Starting worker thread...")
            self.threadpool.start(worker)
            print("Worker started.")

        else:
            self.feedback_info_label.setText("Source and destination folder must be different!")
            self.feedback_info_label.setStyleSheet("color: red; font-weight: bold;")
            print("Warning! Destination folder not found!")
            return



    def exact_match_hashing(self, progress_callback=None):
        self.img_hashes_dict.clear()
        self.duplicates_found = False
        # convert images to hashes and store in list
        if not self.source_files:
            print("No images found. Please select a valid folder.")
            return  # Exit early if there's nothing to process

        try:
            print("Exact Match Hashing started")

            print(f"exact_match_hashing started with progress_callback: {progress_callback}")

            total_files = len(self.source_files)

            for idx, file in enumerate(self.source_files):
                img_hash = self.compute_file_hash(file)
                # sets default value to a key - a list in this case and then updates value if key is found again
                self.img_hashes_dict.setdefault(img_hash, []).append(file)
                # Calculate and emit progress (as percentage)
                if progress_callback:
                    progress = (idx + 1) / total_files * 100
                    progress_callback.emit(progress)
                    print(f"progress: {progress}")

        except Exception as e:
            print(f"Error in exact_match_hashing: {e}")


    def perceptual_hashing(self, progress_callback=None):
        print("Hashing")
        self.img_hashes_dict.clear()
        self.duplicates_found = False
        # convert images to hashes and store in list
        if not self.source_files:
            print("No images found. Please select a valid folder.")
            return  # Exit early if there's nothing to process

        try:
            for file in self.source_files:
                with Image.open(file) as img:
                    img = img.convert("RGB")
                    img_hash = str(imagehash.average_hash(img))

                self.img_hashes_dict.setdefault(img_hash, []).append(file)
        except Exception as e:
            print(f"Error processing {file}: {e}")
            self.feedback_info_label.setText(f"Error processing {file}: {e}")



    def histogram_comparison(self, progress_callback=None):
        self.img_hashes_dict.clear()
        self.duplicates_found = False
        # convert images to hashes and store in list
        if not self.source_files:
            print("No images found. Please select a valid folder.")
            return  # Exit early if there's nothing to process

        for file in self.source_files:
            with Image.open(file) as img:
                img_hash = str(imagehash.phash(img))
            # sets default value to a key - a list in this case and then updates value if key is found again
            self.img_hashes_dict.setdefault(img_hash, []).append(file)




    def find_duplicates(self):
        if not (os.path.exists(self.dest_folder) and os.path.isdir(self.dest_folder)):
            print("Invalid destination folder.")
            return

        self.move_duplicates()


    def move_duplicates(self):
        print("move duplicates")
        moved_files = []
        moved_number = 0

        for hash_value, files in self.img_hashes_dict.items():
            if len(files) > 1:
                self.duplicates_found = True
                for f in files:
                    if not os.path.commonpath([f, self.dest_folder]) == self.dest_folder:
                        shutil.move(f, self.dest_folder)
                        moved_number += 1
                        moved_files.append(f)

        if not self.duplicates_found:
            print("No duplicates found.")
            self.feedback_info_label.setText("No duplicates found.")
            self.feedback_info_label.setStyleSheet("color: orange; font-weight: bold;")

        else:
            print(f"Moved the following files: {moved_files}")
            self.feedback_info_label.setText(f"{moved_number} duplicates found.")
            self.feedback_info_label.setStyleSheet("color: blue; font-weight: bold;")

    @staticmethod
    def compute_file_hash(filepath): # hashing files
        hasher = hashlib.sha256()  # Or hashlib.md5() if you prefer
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):  # Read in chunks for efficiency
                hasher.update(chunk)
        return hasher.hexdigest()

    def update_progress_bar(self, value):
        self.progress_bar.setValue(value)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    detector = DuplicateImagesDetector()
    detector.show()
    sys.exit(app.exec())