import datetime
import os
import shutil
import sys
import hashlib
import traceback
import numpy as np
from PIL import Image
import imagehash

from PyQt6.QtCore import Qt, QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon
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
        self.kwargs["progress_callback"] = self.signals.progress

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            traceback.print_exc()
            exception_type, value = sys.exc_info()[:2]
            self.signals.error.emit((exception_type, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


class DuplicateImagesDetector(QWidget):
    def __init__(self):
        super().__init__()
        # set window name and geometry
        self.setWindowTitle("Duplicated Image Detector")
        self.resize(400, 400)
        self.setWindowIcon(QIcon("compare.ico"))
        self.setFixedSize(self.size())
        self.selected_method = "Exact Match"

        self.source_folder = ""
        self.dest_folder = ""

        self.source_files = []
        self.img_hashes_dict = {}
        self.duplicates_found = False
        self.start_time = None
        self.end_time = None

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
        self.source_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_info_label.setMaximumWidth(400)  # set max width on the info label to prevent UI stretching
        self.source_info_label.setStyleSheet("color: yellow; font-weight: bold;")
        self.source_info_label.setToolTip("Selected source path")
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
        self.dest_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dest_info_label.setMaximumWidth(400)  # set max width on the info label to prevent UI stretching
        self.dest_info_label.setStyleSheet("color: yellow; font-weight: bold;")
        self.dest_info_label.setToolTip("Selected target path")
        self.dest_info_layout.addWidget(self.dest_info_label)

        # comparison method selection
        self.method_group = QGroupBox("Comparison Method") # group box for the radio buttons
        self.method_layout = QVBoxLayout()
        # radio buttons
        self.exact_match_radio = QRadioButton("Exact Match – Finds identical copies. Fast.")
        self.hashing_radio = QRadioButton("Perceptual Hashing – Detects similar images. Slower.")
        self.mean_color = QRadioButton("Mean Color Hash – Compares overall color. Slow.")

        self.exact_match_radio.setChecked(True)  # Default selection
        self.method_group.setDisabled(True)

        self.method_layout.addWidget(self.exact_match_radio)
        self.method_layout.addWidget(self.hashing_radio)
        self.method_layout.addWidget(self.mean_color)

        self.method_group.setLayout(self.method_layout)

        # execute button
        self.execute_comparison_layout = QVBoxLayout()
        self.execute_comparison_button = QPushButton("Execute")
        self.execute_comparison_button.setToolTip("Begin the search.")
        self.execute_comparison_layout.addWidget(self.execute_comparison_button)

        # feedback layout
        self.feedback_layout = QVBoxLayout()
        self.feedback_info_label = QLabel()
        self.feedback_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setRange(0, 100)
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

        # search result details
        self.search_result_info_layout = QVBoxLayout()
        self.search_result_info_label = QLabel()
        self.search_result_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search_result_info_layout.addWidget(self.search_result_info_label)
        self.master_layout.addLayout(self.search_result_info_layout)

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
                            
                            QProgressBar {
                                border: 2px solid gray;
                                border-radius: 5px;
                                text-align: center; /* Puts the percentage text in the center */
                                font-size: 16px;
                                color: black;
                                background-color: lightgray; /* Background behind the bar */
                            }
                                
                            QProgressBar::chunk {
                                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #4caf50, stop:1 #8bc34a);
                            }
                            
                            
                            

}

                            """)

    def event_handler(self):
        self.source_button.clicked.connect(self.open_source_dir)
        self.dest_button.clicked.connect(self.open_dest_dir)
        self.execute_comparison_button.clicked.connect(self.execute_search)
        # connect radio buttons
        self.exact_match_radio.toggled.connect(self.update_method)
        self.hashing_radio.toggled.connect(self.update_method)
        self.mean_color.toggled.connect(self.update_method)


    def update_method(self):
        if self.exact_match_radio.isChecked():
            self.selected_method = "Exact Match"
        elif self.hashing_radio.isChecked():
            self.selected_method = "Perceptual Hashing"
        elif self.mean_color.isChecked():
            self.selected_method = "Mean Color"


    def open_source_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")

        if not (os.path.exists(path) and os.path.isdir(path)):
            self.source_info_label.setText("Invalid source folder.")
            self.source_info_label.setStyleSheet("color: red; font-weight: bold;")
            self.method_group.setEnabled(False)
            print("Invalid source folder.")
            return

        self.source_folder = path
        self.feedback_info_label.clear()

        # truncate path if too long
        if len(self.source_folder) < 39:
            self.source_info_label.setText(f"{self.source_folder}")
        else:
            trunc = f"{self.source_folder[:5]}...{os.path.sep}{os.path.basename(self.source_folder)}"
            self.source_info_label.setText(f"{trunc}")

        self.source_info_label.setStyleSheet("color: green; font-weight: bold;")
        self.source_info_label.setToolTip(self.source_folder) # set tooltip with full path
        self.set_method_group_status()
        print(self.source_folder)


    def open_dest_dir(self):

        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not (os.path.exists(path) and os.path.isdir(path)):
            self.dest_info_label.setText("Invalid destination folder.")
            self.dest_info_label.setStyleSheet("color: red; font-weight: bold;")
            self.method_group.setEnabled(False)
            print("Invalid destination folder.")
            return

        self.dest_folder = path
        self.feedback_info_label.clear()

        if len(self.dest_folder) < 39:
            self.dest_info_label.setText(f"{self.dest_folder}")
        else:
            trunc = f"{self.dest_folder[:5]}...{os.path.sep}{os.path.basename(self.dest_folder)}"
            self.dest_info_label.setText(f"{trunc}")

        self.dest_info_label.setStyleSheet("color: green; font-weight: bold;")
        self.dest_info_label.setToolTip(self.dest_folder)

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
    # ##################################################################################################################
    def execute_search(self):

        if (os.path.isdir(self.source_folder) and os.path.isdir(self.dest_folder)) and \
                self.dest_folder != self.source_folder:
            self.load_file_paths()
            self.feedback_info_label.clear()
            self.feedback_info_label.setStyleSheet("color: orange; font-weight: bold;")

            if not self.source_files:
                print("No files found! Exiting execution.")
                self.feedback_info_label.setText("No images found in the source folder.")
                return

            self.set_worker_thread()
            # clear previous search result details
            self.search_result_info_label.clear()
            # get the start of the search time
            self.start_time = datetime.datetime.now()

        else:
            self.feedback_info_label.setText("Source and destination folder must be different!")
            self.feedback_info_label.setStyleSheet("color: red; font-weight: bold;")
            print("Warning! Destination folder not found!")
            return


    def set_worker_thread(self):
        self.worker = self.set_search_method()  # create worker based on selected search method

        self.worker.signals.progress.connect(self.update_progress_bar)
        self.method_group.setEnabled(False)
        self.worker.signals.finished.connect(self.find_duplicates)

        print("Starting worker thread...")
        self.threadpool.start(self.worker)
        print("Worker started.")

    def set_search_method(self):
        match self.selected_method:
            case "Exact Match":
                print("Starting Exact Match Hashing")
                worker = Worker(self.exact_match_hashing)

            case "Perceptual Hashing":
                print("Starting Perceptual Hashing")
                worker = Worker(self.perceptual_hashing)

            case "Mean Color":
                print("Mean Color Hashing")
                worker = Worker(self.mean_color_hash)

            case _:
                print("Error: No valid method selected!")
                self.feedback_info_label.setText("Invalid comparison method selected.")
                return

        return worker

    # exact hash matching
    ####################################################################################################################
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
                self.feedback_info_label.setText(f"Checking {idx + 1} of {total_files} files.")
                # Calculate and emit progress
                if progress_callback:
                    progress = (idx + 1) / total_files * 100
                    progress_callback.emit(round(progress, 2))
                    #print(f"progress: {round(progress, 2)}")


        except Exception as e:
            print(f"Error in exact_match_hashing: {e}")

    # compute hash
    ####################################################################################################################
    @staticmethod
    def compute_file_hash(filepath):  # hashing files
        hasher = hashlib.sha256()  # Or hashlib.md5()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):  # Read in chunks for efficiency
                hasher.update(chunk)
        return hasher.hexdigest()

    def perceptual_hashing(self, progress_callback=None):
        print("Hashing")
        self.img_hashes_dict.clear()
        self.duplicates_found = False
        # convert images to hashes and store in list
        if not self.source_files:
            print("No images found. Please select a valid folder.")
            return  # exit if nothing to process

        total_files = len(self.source_files)

        try:
            for idx, file in enumerate(self.source_files):
                with Image.open(file) as img:
                    img = img.convert("RGB")
                    img_hash = str(imagehash.average_hash(img))

                self.img_hashes_dict.setdefault(img_hash, []).append(file)
                self.feedback_info_label.setText(f"Checking {idx + 1} of {total_files} files.")
                if progress_callback:
                    progress = (idx + 1) / total_files * 100
                    progress_callback.emit(round(progress, 2))

        except Exception as e:
            print(f"Error processing {file}: {e}")
            self.feedback_info_label.setText(f"Error processing {file}: {e}")



    def mean_color_hash(self, progress_callback=None):
        self.img_hashes_dict.clear()
        self.duplicates_found = False
        # convert images to hashes and store in list
        if not self.source_files:
            print("No images found. Please select a valid folder.")
            return  # Exit early if there's nothing to process
        total_files = len(self.source_files)

        for idx, file in enumerate(self.source_files):
            try:
                img_hash = self.calculate_mean_color_hash(file)
                # sets default value to a key - a list in this case and then updates value if key is found again
                self.img_hashes_dict.setdefault(img_hash, []).append(file)
                self.feedback_info_label.setText(f"Checking {idx + 1} of {total_files} files.")
                if progress_callback:
                    progress = (idx + 1) / total_files * 100
                    progress_callback.emit(round(progress, 2))
                    #print(f"progress: {round(progress, 2)}")

            except Exception as e:
                print(f"Error processing {file}: {e}")
                self.feedback_info_label.setText(f"Error processing {file}: {e}")


    @staticmethod
    def calculate_mean_color_hash(image_path):
        """simple hash based on the mean color of an image."""
        img = Image.open(image_path).convert("RGB")
        img = img.resize((64, 64))  # Resize to normalize data
        mean_color = np.array(img).mean(axis=(0, 1))  # (R, G, B)

        # Convert RGB mean to a simple 6-character hex string
        hash_value = f"{int(mean_color[0]):02X}{int(mean_color[1]):02X}{int(mean_color[2]):02X}"
        return hash_value  # Example: "7BC896"



    def find_duplicates(self):
        if not (os.path.exists(self.dest_folder) and os.path.isdir(self.dest_folder)):
            print("Invalid destination folder.")
            return
        self.move_duplicates()

    # move method
    ####################################################################################################################
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

        self.method_group.setEnabled(True)
        self.estimate_search_time()

        if not self.duplicates_found:
            print("No duplicates found.")
            self.feedback_info_label.setText("No duplicates found.")
            self.feedback_info_label.setStyleSheet("color: orange; font-weight: bold;")

        else:
            print(f"Moved the following files: {moved_files}")
            self.feedback_info_label.setText(f"{moved_number} duplicates found.")
            self.feedback_info_label.setStyleSheet("color: cyan; font-weight: bold;")


    # calculate time for current search
    ####################################################################################################################
    def estimate_search_time(self):
        self.end_time = datetime.datetime.now()
        # print(f"Started at: {self.start_time}, ended at: {self.end_time}")

        # calculate the time the search took
        elapsed_time = self.end_time - self.start_time
        formatted_time = str(elapsed_time).split(".")[0]
        print(f"Search time: {formatted_time}")
        self.search_result_info_label.setText(f"Search time: {formatted_time} for {len(self.source_files)} files.")

    # progress bar
    ####################################################################################################################
    @pyqtSlot(float)
    def update_progress_bar(self, value):
        #print(f"Updating progress bar: {value}")
        self.progress_bar.setValue(int(value))


if __name__ == "__main__":
    app = QApplication([])
    detector = DuplicateImagesDetector()
    detector.show()
    sys.exit(app.exec())