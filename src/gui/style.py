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
  border: none;                 /* no extra edge for notes */
  border-radius: 0;
  background: transparent;
  color: {rgb("gray")};
}}
#NotesView {{                      /* ensure notes obey no-border */
  border: none;
  background: transparent;
  color: {rgb("gray")};
}}

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

/* -------- Muted gray labels (e.g., Gefäße, Transparenz) -------- */
#MutedLabel {{
  color: {rgb("gray")};
}}

/* Demo badge: match exact height and styling of patient pill */

#Badge_Demo {{
  background: {rgb("light_light_gray")};
  color: {rgb("gray")};
  padding: 4px 10px;          /* exactly same as PatientPill */
  border-radius: 12px;        /* exactly same as PatientPill */
  font-size: 12px;            /* exactly same as PatientPill */
  margin-left: 6px;
  min-height: 20px;           /* match the computed height of PatientPill */
  max-height: 20px;           /* prevent growing taller */
  qproperty-alignment: 'AlignVCenter';
}}

/* Ensure title has proper styling for the first row */
#TopTitle {{
  font-weight: 600;
  font-size: 18px;            /* slightly larger since it's now prominent */
  color: {rgb("gray")};
  margin-bottom: 2px;
}}

/* Camera status text (left side, next to camera icon) */
#CameraStatus {{
  color: {rgb("light_gray")};        /* muted by default */
  font-size: 13px;
  padding-left: 6px;
  padding-right: 6px;
  min-width: 60px;
  max-width: 260px;
  qproperty-alignment: 'AlignVCenter'; /* keep it vertically centered */
}}

/* when set to connected */
#CameraStatus[connected="true"], #CameraStatus[connected=true] {{
  color: {rgb("dark_blue")};
  font-weight: 600;
}}

#Badge_Patient {{
  background: {rgb("gray")};
  color: {rgb("white")};
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}}

#PatientPill {{
  background: {rgb("gray")};
  color: {rgb("white")};
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
}}
/* Camera badge: light gray when disconnected, light blue when connected */
#RecordPill {{
  background: {rgb("light_gray")};
  color: {rgb("white")};
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 12px;
  border: none;
}}
#RecordPill[connected="true"], #RecordPill[connected=true] {{
  background: {rgb("light_blue")};
  color: {rgb("white")};
}}
#RecordPill[stopped="true"], #RecordPill[stopped=true] {{
  background: {rgb("white")};
  color: {rgb("gray")};
  border: 1px solid {rgb("light_gray")};
}}
#RecordPill QLabel {{ color: inherit; }}

/* Camera status text (left side, next to camera icon) */
#CameraStatus {{
  color: {rgb("light_gray")};        /* muted by default */
  font-size: 13px;
  padding-left: 6px;
  padding-right: 6px;
  min-width: 80px;
  max-width: 220px;
  qproperty-alignment: 'AlignVCenter'; /* keep it vertically centered */
}}

/* when set to connected */
#CameraStatus[connected="true"], #CameraStatus[connected=true] {{
  color: {rgb("dark_blue")};
  font-weight: 600;
}}

/* optional explicit muted property (if you want a softer gray) */
#CameraStatus[muted="true"], #CameraStatus[muted=true] {{
  color: {rgb("light_gray")};
  font-weight: 400;
}}

/* Screenshot button: white → light gray hover → dark gray press */
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

/* ROI button: hover light-light blue, checked/pressed light blue */
#ROIButton {{
  background: {rgb("light_gray")};
  color: {rgb("gray")};
  border: 1px solid {rgb("light_gray")};
  border-radius: 8px;
  padding: 6px 12px;
}}
#ROIButton:hover {{
  background: {rgb("light_light_blue")};
}}
#ROIButton:checked, #ROIButton:pressed {{
  background: {rgb("light_blue")};
  color: {rgb("white")};
  border: none;
}}
"""
