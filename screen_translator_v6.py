import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import keyboard
import pytesseract
from PIL import ImageGrab, ImageTk, Image 
import threading
import time
import deepl 
import pandas as pd
import config # config.py 파일 임포트 (별도로 존재해야 함)


# ==========================================
# ContextWindow 클래스 (번역 결과 상세 오버레이 창)
# ==========================================
class ContextWindow(tk.Toplevel):
    def __init__(self, master, img, ocr_data, translated_text):
        super().__init__(master)
        self.title("번역 결과 상세")
        self.attributes('-topmost', True)
        self.geometry("800x600") 
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        
        self.img = img
        self.ocr_data = ocr_data 
        self.translated_text = translated_text
        self.display_mode = tk.StringVar(value="OverlayView") 

        self.create_widgets()
        self.display_mode.trace_add("write", self.update_view) 

    def create_widgets(self):
        # 1. 모드 선택 UI
        mode_frame = ttk.Frame(self)
        mode_frame.pack(fill='x', padx=10, pady=(5, 0))
        
        ttk.Label(mode_frame, text="결과 표시 방식:").pack(side='left', padx=(0, 10))
        
        ttk.Radiobutton(mode_frame, text="1. 텍스트 뷰 (원본/번역 분리)", 
                         variable=self.display_mode, value="TextView").pack(side='left', padx=5)
        ttk.Radiobutton(mode_frame, text="2. 오버레이 뷰 (이미지 위에 덮기) Beta", 
                         variable=self.display_mode, value="OverlayView").pack(side='left', padx=5)

        # 2. 뷰를 담을 메인 프레임
        self.main_view_frame = ttk.Frame(self)
        self.main_view_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # 3. 초기 뷰 생성
        self.update_view()

    def clear_view(self):
        """메인 뷰 프레임의 모든 위젯을 제거합니다."""
        for widget in self.main_view_frame.winfo_children():
            widget.destroy()
    
    def update_view(self, *args):
        """선택된 모드에 따라 뷰를 다시 그립니다."""
        self.clear_view()
        
        mode = self.display_mode.get()
        if mode == "TextView":
            self.create_text_view()
        elif mode == "OverlayView":
            self.create_overlay_view()

    def create_text_view(self):
        """텍스트 뷰 (기존 상세 창 레이아웃) 생성"""
        main_frame = self.main_view_frame
        
        # 1. 캡처 이미지 섹션 (왼쪽)
        img_frame = ttk.LabelFrame(main_frame, text="캡처 화면")
        img_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        self.canvas = tk.Canvas(img_frame, bg='white', relief=tk.SUNKEN, borderwidth=1)
        self.canvas.pack(fill='both', expand=True)
        self.display_image(self.img, self.canvas) 
        self.canvas.bind('<Configure>', lambda e, c=self.canvas: self.display_image(self.img, c))

        # 2. 번역 텍스트 섹션 (오른쪽)
        text_frame = ttk.LabelFrame(main_frame, text="번역 결과")
        text_frame.pack(side='right', fill='y', padx=5, pady=5)
        
        ocr_text_list = self.ocr_data['text'].dropna().tolist() if self.ocr_data is not None else ["OCR 데이터 없음"]
        
        ttk.Label(text_frame, text="[원본 OCR 텍스트]", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(5,0))
        ocr_area = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=8, font=("Malgun Gothic", 9))
        ocr_area.insert(tk.INSERT, "\n".join(ocr_text_list)) 
        ocr_area.config(state=tk.DISABLED)
        ocr_area.pack(fill='x', padx=5, pady=2)
        
        ttk.Label(text_frame, text="[번역된 텍스트]", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10,0))
        trans_area = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=15, font=("Malgun Gothic", 11, 'bold'))
        trans_area.insert(tk.INSERT, self.translated_text)
        trans_area.config(state=tk.DISABLED)
        trans_area.pack(fill='both', expand=True, padx=5, pady=2)


    def create_overlay_view(self):
        """오버레이 뷰 (이미지 위에 번역 텍스트 덮기) 생성"""
        main_frame = self.main_view_frame
        
        overlay_canvas = tk.Canvas(main_frame, bg='black') 
        overlay_canvas.pack(fill='both', expand=True)

        self.display_overlay_image(self.img, overlay_canvas, self.ocr_data, self.translated_text)
        
        overlay_canvas.bind('<Configure>', 
                            lambda e, c=overlay_canvas: self.display_overlay_image(self.img, c, self.ocr_data, self.translated_text))


    def display_image(self, img, canvas):
        """일반 뷰에서 이미지를 표시"""
        if img is None: return
        canvas.delete("all")
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        if canvas_width < 10 or canvas_height < 10: return

        img_width, img_height = img.size
        ratio_w = canvas_width / img_width
        ratio_h = canvas_height / img_height
        ratio = min(ratio_w, ratio_h)
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)
        
        resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(resized_img)
        canvas.create_image(canvas_width/2, canvas_height/2, image=self.photo, anchor='center')
        canvas.image = self.photo


    def display_overlay_image(self, img, canvas, ocr_data, translated_text_full):
        """
        오버레이 뷰에서 이미지 위에 번역 텍스트를 덮습니다.
        """
        if img is None: return
        canvas.delete("all")
        
        # 캔버스 크기, 이미지 로딩, 비율/위치 계산 로직은 동일
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        if canvas_width < 10 or canvas_height < 10: return
        
        img_width, img_height = img.size
        ratio_w = canvas_width / img_width
        ratio_h = canvas_height / img_height
        ratio = min(ratio_w, ratio_h)
        
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)

        resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.overlay_photo = ImageTk.PhotoImage(resized_img)
        
        img_start_x = (canvas_width - new_width) // 2
        img_start_y = (canvas_height - new_height) // 2

        canvas.create_image(img_start_x, img_start_y, image=self.overlay_photo, anchor='nw')
        canvas.image = self.overlay_photo
        
        # --- OCR 데이터 및 줄 불일치 예외 처리 ---
        translated_lines = translated_text_full.split('\n')
        valid_ocr_lines = ocr_data.dropna(subset=['text'])
        
        if len(translated_lines) != len(valid_ocr_lines):
            # 줄 수가 맞지 않으면 중앙에 표시하는 예비 로직으로 대체
            x_pos = img_start_x + new_width / 2
            y_pos = img_start_y + new_height / 4
            canvas.create_text(x_pos, y_pos, 
                                text="[줄 수 불일치] " + translated_text_full, 
                                fill="red", font=("Malgun Gothic", 12, "bold"),
                                width=new_width * 0.9, justify="center", anchor="n")
            return
            
        # 3. 줄 단위로 순회하며 텍스트를 이미지 위에 덮어씁니다.
        
        # --- 💡 폰트 크기 및 패딩 설정 ---
        MIN_FONT_SIZE = 10 
        MAX_FONT_SIZE = 24 
        PADDING_Y = 8   
        MIN_GAP = 2     

        last_drawn_y_end = img_start_y
        
        for i, (index, line) in enumerate(valid_ocr_lines.iterrows()):
            if i >= len(translated_lines):
                break

            trans_text = translated_lines[i].strip()
            if not trans_text:
                continue 
            
            scale_factor = ratio 

            # 캔버스상의 원본 OCR 바운딩 박스 위치 계산
            bbox_x = line['left'] * scale_factor + img_start_x
            bbox_y = line['top'] * scale_factor + img_start_y
            bbox_width = line['width'] * scale_factor
            bbox_height = line['height'] * scale_factor
            
            # 1. 폰트 크기 결정: 
            optimal_font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, int(bbox_height * 0.8))) 
            font_tuple = ("Malgun Gothic", optimal_font_size, "bold")

            # 텍스트 중앙 X 위치
            text_x = bbox_x + bbox_width / 2
            text_draw_width = bbox_width * 0.95 
            
            # --- 텍스트 실제 높이 측정 ---
            temp_text_id = canvas.create_text(0, 0, 
                                            text=trans_text,
                                            font=font_tuple,
                                            width=text_draw_width,
                                            anchor="nw",
                                            fill="")
            
            temp_bbox = canvas.bbox(temp_text_id)
            actual_text_height = (temp_bbox[3] - temp_bbox[1]) if temp_bbox else bbox_height
            canvas.delete(temp_text_id)

            # --- Y축 독립성 확보 및 최종 박스 경계 계산 ---
            current_ideal_y_start = bbox_y - PADDING_Y 
            safe_y_start = last_drawn_y_end + MIN_GAP
            final_y_start = max(current_ideal_y_start, safe_y_start) 
            final_y_end = final_y_start + actual_text_height + (PADDING_Y * 2) 
            final_text_center_y = (final_y_start + final_y_end) / 2
            
            # 6. 배경 박스 그리기
            canvas.create_rectangle(bbox_x, final_y_start, 
                                    bbox_x + bbox_width, final_y_end, 
                                    fill='white', outline='white') 
            
            # 7. 번역 텍스트를 중앙에 표시
            canvas.create_text(text_x, final_text_center_y, 
                                text=trans_text,
                                fill="black", 
                                font=font_tuple, 
                                width=text_draw_width, 
                                justify="center",
                                anchor="center")
                                
            last_drawn_y_end = final_y_end


# -------------------------------------------------------------
# TranslatorApp 클래스 (모든 수정 사항 반영)
# -------------------------------------------------------------

class TranslatorApp(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.master.title("화면 번역기 설정 (DeepL 공식)")
        self.pack(fill="both", expand=True)

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # --- A. 상태 표시 섹션 ---
        self.status_label = ttk.Label(self, text="초기화 중...", anchor="w", foreground="gray")
        self.status_label.pack(side=tk.BOTTOM, fill="x")
        
        self.context_window = None 
        self.translator = None 
        self.api_check = False 
        self.is_running = False
        
        # --- B. 설정 섹션 ---
        self._setup_settings_ui()
        
        # --- C. 메인 컨트롤 섹션 ---
        control_frame = ttk.LabelFrame(self, text="📝 번역 컨트롤")
        control_frame.pack(padx=10, pady=10, fill="x")

        # 캡처 방식 설정
        lf_capture = ttk.LabelFrame(control_frame, text="1. 캡처 방식 선택")
        lf_capture.pack(fill="x", padx=5, pady=5)
        self.capture_mode = tk.StringVar(value="region") 
        ttk.Radiobutton(lf_capture, text="영역 선택 (마우스 드래그)", variable=self.capture_mode, value="region").pack(anchor="w", padx=5)
        ttk.Radiobutton(lf_capture, text="전체 화면", variable=self.capture_mode, value="full").pack(anchor="w", padx=5)

        # 번역 언어 설정 (원본 언어 코드 필드 추가)
        lf_lang = ttk.LabelFrame(control_frame, text="2. 번역 언어 설정")
        lf_lang.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(lf_lang, text="대상 언어 코드 (DeepL, KO, EN-US 등)").pack(anchor="w", padx=5)
        self.target_lang = tk.StringVar(value="KO")
        ttk.Entry(lf_lang, textvariable=self.target_lang).pack(fill="x", padx=5, pady=2)
        
        ttk.Label(lf_lang, text="원본 언어 코드 (Tesseract, eng, kor, jpn 등)").pack(anchor="w", padx=5, pady=(10,0))
        self.source_ocr_lang = tk.StringVar(value="eng")
        ttk.Entry(lf_lang, textvariable=self.source_ocr_lang).pack(fill="x", padx=5, pady=2)


        # 단축키 설정 (키 입력 버튼 추가)
        lf_hotkey = ttk.LabelFrame(control_frame, text="3. 단축키 설정")
        lf_hotkey.pack(fill="x", padx=5, pady=5)
        
        self.hotkey_var = tk.StringVar(value="ctrl+alt+t")
        
        hotkey_entry = ttk.Entry(lf_hotkey, textvariable=self.hotkey_var)
        hotkey_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        self.btn_capture_hotkey = ttk.Button(lf_hotkey, text="단축키 입력 (클릭 후 키 입력)", 
                                             command=self.start_hotkey_capture)
        self.btn_capture_hotkey.grid(row=0, column=1, padx=5, pady=5)
        
        lf_hotkey.grid_columnconfigure(0, weight=1) 

        # 실행 버튼
        self.btn_start = ttk.Button(control_frame, text="설정 적용 및 감지 시작", command=self.toggle_listening)
        self.btn_start.pack(fill="x", padx=5, pady=10)


    def start_hotkey_capture(self):
        """단축키 입력을 대기하는 모드로 전환하고 키보드 이벤트를 감지합니다."""
        
        self.status_label.config(text="단축키 입력을 대기합니다... (취소: ESC)", foreground="orange")
        self.btn_capture_hotkey.config(text="입력 대기 중...", state=tk.DISABLED)
        
        # 키 이벤트 감지 시작
        self.key_listener_hook = keyboard.hook(self._capture_first_hotkey_event)
        
        # ESC 키를 눌러 캡처 모드 취소 기능 추가
        self.esc_hook = keyboard.add_hotkey('esc', self.cancel_hotkey_capture, suppress=True)


    def _capture_first_hotkey_event(self, event):
        """가장 먼저 인식된 키 조합을 단축키로 설정합니다. (keyboard.remove_hotkey 적용)"""
        
        if event.event_type == keyboard.KEY_DOWN:
            current_hotkey = keyboard.get_hotkey_name()
            
            if current_hotkey and current_hotkey != 'esc':
                keyboard.unhook(self.key_listener_hook)
                # 단축키 해제 오류 수정: remove_hotkey 사용
                keyboard.remove_hotkey(self.esc_hook)
                
                self.master.after(0, lambda: self._apply_captured_hotkey(current_hotkey))
                
                return False 

    def _apply_captured_hotkey(self, hotkey_name):
        """캡처된 단축키를 변수에 설정하고 UI를 원래대로 복원합니다."""
        self.hotkey_var.set(hotkey_name)
        self.status_label.config(text=f"단축키 설정 완료: {hotkey_name}", foreground="blue")
        self.btn_capture_hotkey.config(text="단축키 입력 (클릭 후 키 입력)", state=tk.NORMAL)
        
    def cancel_hotkey_capture(self):
        """ESC 키 등으로 단축키 캡처 모드를 취소합니다. (keyboard.remove_hotkey 적용)"""
        
        if hasattr(self, 'key_listener_hook'):
            keyboard.unhook(self.key_listener_hook)
            
        if hasattr(self, 'esc_hook'):
            try:
                # 단축키 해제 오류 수정: remove_hotkey 사용
                keyboard.remove_hotkey(self.esc_hook)
            except KeyError:
                pass
            
        self.master.after(0, lambda: self.status_label.config(text="단축키 설정이 취소되었습니다.", foreground="gray"))
        self.master.after(0, lambda: self.btn_capture_hotkey.config(text="단축키 입력 (클릭 후 키 입력)", state=tk.NORMAL))


    def _setup_settings_ui(self):
        """설정 입력 필드를 구성합니다."""
        settings_frame = ttk.LabelFrame(self, text="⚙️ 엔진/API 설정 (저장 필수)") 
        settings_frame.pack(padx=10, pady=10, fill="x")
        
        # 1. Tesseract 경로 입력
        tess_label = ttk.Label(settings_frame, text="Tesseract 경로 (.exe):")
        tess_label.grid(row=0, column=0, sticky="w", pady=2)
        
        self.tesseract_path_var = tk.StringVar(value=config.get_tesseract_path())
        tess_entry = ttk.Entry(settings_frame, textvariable=self.tesseract_path_var, width=45)
        tess_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        
        tess_button = ttk.Button(settings_frame, text="찾아보기", command=self.browse_tesseract_path)
        tess_button.grid(row=0, column=2, padx=5, pady=2)

        # 2. DeepL API 키 입력
        api_label = ttk.Label(settings_frame, text="DeepL API 키:")
        api_label.grid(row=1, column=0, sticky="w", pady=2)
        
        self.api_key_var = tk.StringVar(value=config.get_deepl_key())
        api_entry = ttk.Entry(settings_frame, textvariable=self.api_key_var, width=45, show="*")
        api_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        
        # 3. 설정 저장 버튼
        save_button = ttk.Button(settings_frame, text="설정 저장", command=self.save_settings, style='Accent.TButton')
        save_button.grid(row=1, column=2, padx=5, pady=2)
        
        settings_frame.grid_columnconfigure(1, weight=1) 
        
        self.save_settings(initial=True) 

    def browse_tesseract_path(self):
        """Tesseract 실행 파일 경로를 탐색합니다."""
        filepath = filedialog.askopenfilename(
            title="Tesseract 실행 파일 (tesseract.exe) 선택",
            filetypes=(("실행 파일", "*.exe"), ("모든 파일", "*.*"))
        )
        if filepath:
            self.tesseract_path_var.set(filepath)
            self.status_label.config(text=f"Tesseract 경로 임시 설정: {filepath}")

    def save_settings(self, initial=False):
        """현재 Entry 위젯의 내용을 설정 파일에 저장하고 적용합니다."""
        tess_path = self.tesseract_path_var.get()
        deepl_key = self.api_key_var.get()
        
        current_config = {
            'tesseract_path': tess_path,
            'deepl_api_key': deepl_key
        }
        
        if not initial:
            config.save_config(current_config)
        
        # 설정 적용: pytesseract 경로와 DeepL Translator 인스턴스 업데이트
        try:
            if tess_path:
                pytesseract.pytesseract.tesseract_cmd = tess_path
            
            if deepl_key:
                self.translator = deepl.Translator(deepl_key)
                self.api_check = True
            else:
                 self.api_check = False
                 raise ValueError("DeepL API 키가 설정되지 않았습니다.")
                 
            if not initial:
                messagebox.showinfo("설정 저장 완료", "설정이 성공적으로 저장 및 적용되었습니다.")
                self.status_label.config(text="설정 저장 완료. 감지 시작 가능.", foreground="black")
            else:
                self.status_label.config(text="설정 불러오기 완료.", foreground="gray")


        except ValueError as e:
            if not initial:
                messagebox.showerror("DeepL 오류", str(e))
            self.status_label.config(text="DeepL API 키 오류! 확인 필요.", foreground="red")
        except Exception as e:
            if not initial:
                messagebox.showerror("오류", f"설정 적용 중 오류 발생: {e}")
            self.status_label.config(text="설정 적용 오류.", foreground="red")
            
    def toggle_listening(self):
        # 감지 시작 전 필수 설정값 확인
        hotkey = self.hotkey_var.get()
        tess_path = self.tesseract_path_var.get()
        deepl_key = self.api_key_var.get()
        
        if not tess_path or not deepl_key or not self.api_check:
            messagebox.showerror("설정 필수", "Tesseract 경로와 DeepL API 키를 입력하고 '설정 저장' 버튼을 눌러주세요.")
            return

        # 기존 toggle_listening 로직
        if self.is_running:
            try:
                keyboard.unhook_all()
                self.is_running = False
                self.btn_start.config(text="설정 적용 및 감지 시작", style='TButton')
                self.status_label.config(text="대기 중...", foreground="gray")
            except Exception as e:
                messagebox.showerror("오류", f"단축키 해제 중 오류 발생: {e}")
        else:
            try:
                keyboard.unhook_all()
                keyboard.add_hotkey(hotkey, self.run_translation_process)
                self.is_running = True
                self.btn_start.config(text="감지 중지", style='Accent.TButton')
                self.status_label.config(text=f"단축키 감지 중: {hotkey}", foreground="green")
            except Exception as e:
                messagebox.showerror("오류", f"단축키 등록 중 오류 발생. 단축키({hotkey})를 확인하세요. (예: ctrl+alt+t)")

    def run_translation_process(self):
        if not self.is_running:
            return

        img = None
        self.master.after(0, lambda: self.status_label.config(text="캡처/번역 처리 중...", foreground="blue"))

        if self.capture_mode.get() == "full":
            img = ImageGrab.grab()
            threading.Thread(target=self.process_image, args=(img,)).start()
        else:
            SnippingTool(self.master, self.process_image)


    def process_image(self, img):
        """
        이미지에서 OCR 데이터를 줄 단위로 그룹화하고 DeepL로 번역합니다.
        OCR 언어 코드를 설정 값에서 가져와 사용하도록 수정되었습니다.
        """
        if img is None: 
            self.master.after(0, lambda: self.status_label.config(text="대기 중...", foreground="gray"))
            return

        ocr_data_for_context = None
        translated = ""
        
        # 설정된 OCR 언어 코드를 가져옵니다.
        ocr_lang_code = self.source_ocr_lang.get() 
        
        try:
            # 1. OCR (위치 정보가 포함된 데이터프레임 받기)
            data = pytesseract.image_to_data(img, lang=ocr_lang_code, output_type=pytesseract.Output.DATAFRAME)
            
            words = data[data.level == 5].dropna(subset=['text']) 
            
            line_groups = words.groupby(['page_num', 'block_num', 'par_num', 'line_num'])
            
            full_ocr_text = ""
            line_data_list = [] 
            
            for name, group in line_groups:
                line_text = " ".join(group['text'].tolist()) 
                
                if line_text.strip():
                    full_ocr_text += line_text + "\n" 
                    
                    # 줄 전체의 바운딩 박스 계산:
                    x1 = group['left'].min()
                    y1 = group['top'].min()
                    x2 = (group['left'] + group['width']).max()
                    y2 = (group['top'] + group['height']).max()
                    
                    line_data_list.append({
                        'text': line_text,
                        'left': x1,
                        'top': y1,
                        'width': x2 - x1,
                        'height': y2 - y1
                    })

            ocr_data_for_context = pd.DataFrame(line_data_list)
            
            if not full_ocr_text.strip():
                 self.master.after(0, lambda: self.show_context_window(img, None, f"번역할 텍스트를 찾지 못했습니다. (OCR 언어: {ocr_lang_code})"))
                 return
            
            # 2. 번역 (self.translator 사용)
            result = self.translator.translate_text(
                text=full_ocr_text.strip(), 
                target_lang=self.target_lang.get()
            )
            translated = result.text
            
            # 3. 결과 출력
            self.master.after(0, lambda: self.show_context_window(img, ocr_data_for_context, translated))
            
        except deepl.exceptions.DeepLException as e:
            error_message = str(e)
            self.master.after(0, lambda msg=error_message: self.show_context_window(img, None, f"DeepL API 오류: {msg}"))
            
        except pytesseract.TesseractError as e:
             error_message = str(e)
             tess_path_current = self.tesseract_path_var.get()
             self.master.after(0, lambda msg=error_message: self.show_context_window(img, None, f"Tesseract OCR 오류: {msg}. OCR 언어({ocr_lang_code}) 또는 경로({tess_path_current})를 확인하세요."))
            
        except Exception as e:
            error_message = str(e)
            self.master.after(0, lambda msg=error_message: self.show_context_window(img, None, f"OCR/시스템 오류: {type(e).__name__}: {msg}"))
        
        finally:
             self.master.after(0, lambda: self.status_label.config(text=f"단축키 감지 중: {self.hotkey_var.get()}", foreground="green") if self.is_running else self.status_label.config(text="대기 중...", foreground="gray"))

    def show_context_window(self, img, ocr_data, translated_text):
        """새로운 상세 창을 띄웁니다."""
        for child in self.master.winfo_children():
            if isinstance(child, ContextWindow):
                child.destroy()
        
        ContextWindow(self.master, img, ocr_data, translated_text)

    def on_closing(self):
        """프로그램 종료 시 설정을 저장하고 창을 닫습니다."""
        self.save_settings(initial=True)
        self.master.destroy() 


# SnippingTool 클래스 (이전 코드와 동일)
class SnippingTool(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.attributes('-fullscreen', True)
        self.attributes('-alpha', 0.3)
        self.configure(bg='black')
        self.attributes('-topmost', True)
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.canvas = tk.Canvas(self, cursor="cross", bg="grey11")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.bind("<Escape>", lambda e: self.destroy())
        self.parent = parent
        
    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='red', width=2)

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        self.destroy() 
        self.parent.deiconify() # 메인 창 다시 표시
        
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        if (x2 - x1) < 10 or (y2 - y1) < 10:
            return
            
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        
        threading.Thread(target=self.callback, args=(img,)).start()


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use('vista') 
    except:
        style.theme_use('clam')
        
    # 설정 저장 버튼 스타일 (글자색 수정 반영)
    style.configure('Accent.TButton', background='green', foreground='black') 
    style.map('Accent.TButton', 
              background=[('active', 'dark green')], 
              foreground=[('active', 'white')])

    app = TranslatorApp(root)
    root.mainloop()