from .colors import rgb

STYLE = f"""
/* -------- App chrome -------- */
QMainWindow {{
  background: {rgb("light_light_gray")};
}}
#TopBar {{
  background: {rgb("white")};
  border-bottom: 1px solid {rgb("light_gray")};
  color: {rgb("gray")};
}}
#Footer {{
  background: {rgb("light_light_gray")};
  border-top: 1px solid {rgb("light_light_gray")};
  color: {rgb("gray")};
  font-size: 11px;
  padding: 3px 0;
}}
#Footer QLabel {{
  color: {rgb("gray")};
  background: transparent;
  border: none;
}}
QStatusBar::item {{ border: 0; border-radius: 0; background: transparent; }}

/* -------- Cards -------- */
#Card {{
  background: {rgb("white")};
  border: 1px solid {rgb("light_gray")};
  border-radius: 12px;
}}
#Header {{
  background: {rgb("white")};
  border-bottom: 1px solid {rgb("light_gray")};
}}
#Card > #Header {{
  border-top-left-radius: 12px;
  border-top-right-radius: 12px;
}}
#Card > #CardBody {{
  border-bottom-left-radius: 12px;
  border-bottom-right-radius: 12px;
}}
#HeaderTitle {{
  font-weight: 600;
  font-size: 16px;
  color: {rgb("gray")};
}}

/* -------- Content placeholders -------- */
#VideoArea, #ModelArea {{
  background: {rgb("white")};
  border: 1px dashed {rgb("white")};
  border-radius: 10px;
  color: {rgb("gray")};
}}

/* -------- Form controls -------- */
QLineEdit {{
  padding: 8px 10px;
  border: 1px solid {rgb("light_gray")};
  border-radius: 8px;
  background: {rgb("white")};
  color: {rgb("gray")};
}}
QPlainTextEdit {{
  border: none;
  border-radius: 0;
  background: transparent;
  color: {rgb("gray")};
}}
#NotesView {{
  border: none;
  background: transparent;
  color: {rgb("gray")};
}}

/* Slider */
QSlider::groove:horizontal {{
  height: 6px;
  background: {rgb("light_gray")};
  border-radius: 3px;
}}
QSlider::handle:horizontal {{
  background: {rgb("dark_blue")};
  width: 16px; height:16px;
  margin: -6px 0;
  border-radius: 8px;
}}

/* -------- Muted gray labels -------- */
#MutedLabel {{ color: {rgb("gray")}; }}

/* Demo badge */
#Badge_Demo {{
  background: {rgb("light_light_gray")};
  color: {rgb("gray")};
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  margin-left: 6px;
  min-height: 20px;
  max-height: 20px;
  qproperty-alignment: 'AlignCenter';
}}

/* Title */
#TopTitle {{
  font-weight: 600;
  font-size: 18px;
  color: {rgb("gray")};
  margin-bottom: 2px;
}}

#Badge_Patient, #PatientPill {{
  background: {rgb("gray")};
  color: {rgb("white")};
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
}}

/* Buttons */
#ShotBtn {{
  background: {rgb("white")};
  color: {rgb("gray")};
  border: 1px solid {rgb("light_gray")};
  border-radius: 8px;
  padding: 4px 12px;
}}
#ShotBtn:hover {{
  background: {rgb("light_light_gray")};
}}
#ShotBtn:pressed {{
  background: {rgb("light_gray")};
  color: {rgb("white")};
  border: 1px solid {rgb("light_gray")};
}}

#ROIButton {{
  background: {rgb("light_gray")};
  color: {rgb("gray")};
  border: 1px solid {rgb("light_gray")};
  border-radius: 8px;
  padding: 6px 12px;
}}
#ROIButton:hover {{
  background: {rgb("light_light_blue")};
  border: 1px solid {rgb("light_light_blue")};
}}
#ROIButton:checked, #ROIButton:pressed {{
  background: {rgb("light_blue")};
  color: {rgb("white")};
  border: none;
}}

#OpenVideoButton {{
  background: {rgb("gray")};
  color: {rgb("white")};
  border: 1px solid {rgb("gray")};
  border-radius: 8px;
  padding: 6px 6px;
}}
#OpenVideoButton:hover {{
  background: {rgb("light_gray")};
  border: 1px solid {rgb("light_gray")};
  color: {rgb("white")};
}}
#OpenVideoButton:checked, #OpenVideoButton:pressed {{
  background: {rgb("light_light_gray")};
  color: {rgb("light_gray")};
  border: none;
}}
"""
