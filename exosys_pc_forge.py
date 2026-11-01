import os
import sys
import time
import math
import json
import shutil
import socket
import struct
import random
import base64
import threading
import subprocess
import urllib.parse
from io import BytesIO
from pathlib import Path
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# =============================================================================
# 0. AUTO-INSTALADOR DE DEPENDENCIAS
# =============================================================================
REQUIRED_BASE_PACKAGES = [
    ("numpy", "numpy"),
    ("PIL", "Pillow"),
    ("requests", "requests"),
    ("numba", "numba"),
]

def ensure_dependencies():
    missing = []
    for mod_name, pip_name in REQUIRED_BASE_PACKAGES:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", *missing])

    need_flet_fix = False
    try:
        import flet as _ft_test
        if not hasattr(_ft_test, "app") or not hasattr(_ft_test, "FilePickerResultEvent"):
            need_flet_fix = True
    except ImportError:
        need_flet_fix = True

    if need_flet_fix:
        subprocess.call([
            sys.executable, "-m", "pip", "uninstall", "-y",
            "flet", "flet-desktop", "flet-cli", "flet-web", "flet-core", "flet-runtime"
        ])
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--no-cache-dir",
            "flet==0.25.2", "flet-desktop==0.25.2"
        ])
        sys.exit(subprocess.call([sys.executable, *sys.argv]))

ensure_dependencies()

import numpy as np
import requests
from requests.adapters import HTTPAdapter
from PIL import Image
import flet as ft

try:
    from numba import njit
    HAS_NUMBA = True
except Exception:
    HAS_NUMBA = False

# =============================================================================
# 0B. DICCIONARIO MULTILENGUAJE (ES, EN, ZH, JA, HI, FR, AR, RU)
# =============================================================================
I18N = {
    "es": {
        "step0_title": "PASO 0 — SELECCIONA TU IDIOMA",
        "step0_sub": "Elige tu idioma para comenzar. El asistente te guiará paso a paso.",
        "step1_title": "PASO 1 — CONECTAR CON TU TELÉFONO",
        "step1_sub": "Cuando envíes tu selección desde el teléfono, esta ventana avanzará sola al Paso 2.",
        "cred_box_title": "DATOS DE CONEXIÓN PARA TU TELÉFONO",
        "ip_wifi_lbl": "DIRECCIÓN IP (WI-FI / RED LOCAL):",
        "pin_lbl": "CÓDIGO PIN:",
        "ip_usb_lbl": "CONEXIÓN POR CABLE USB:",
        "usb_wait": "Se activará al encender 'Compartir conexión por USB' en tu celular",
        "opt_a_title": "OPCIÓN A: POR WI-FI O HOTSPOT",
        "opt_a_body": "1. Conecta tu teléfono y esta PC a la misma red Wi-Fi (o al Hotspot de tu celular).\n2. En la app del teléfono toca 'Enviar a PC'.\n3. El programa pasará automáticamente al Paso 2.",
        "opt_b_title": "OPCIÓN B: POR CABLE USB",
        "opt_b_body": "1. Conecta tu teléfono a la PC con un cable USB.\n2. En los ajustes del teléfono activa 'Anclaje por USB'.\n3. Toca 'Enviar a PC' en la aplicación.",
        "opt_c_title": "OPCIÓN C: ABRIR ARCHIVO GUARDADO (.JSON)",
        "opt_c_body": "Si guardaste el pedido como archivo o quieres reanudar un vault_meta.json:",
        "btn_pick_file": "BUSCAR ARCHIVO .JSON EN LA PC",
        "waiting_order": "Esperando que envíes la selección desde tu teléfono...",
        "order_ready": "Pedido cargado: {name}  |  Modo: {mode_str}  |  Peso aprox.: {mb:.1f} MB",
        "btn_to_step2": "CONTINUAR AL PASO 2: ELEGIR DISCO >>",
        "btn_to_step4_direct": "IR A MIS MAPAS GUARDADOS (PASO 4)",
        "step2_title": "PASO 2 — ELEGIR EN QUÉ DISCO DE LA PC SE DESCARGARÁ TEMPORALMENTE",
        "dd_pc_drive": "Disco de esta computadora donde se guardará la descarga temporal (EXOSYS_VAULT)",
        "btn_refresh_drives": "ACTUALIZAR DISCOS",
        "space_ok": "Espacio libre en PC: {pc_gb:.1f} GB  |  Espacio requerido: {req_mb:.1f} MB  [ESPACIO SUFICIENTE]",
        "space_low": "Espacio libre en PC: {pc_gb:.1f} GB  |  Espacio requerido: {req_mb:.1f} MB  [ESPACIO INSUFICIENTE]",
        "space_idle": "Espacio libre en disco de PC: {pc_gb:.1f} GB  |  Espacio libre en memoria SD destino: {sd_gb:.1f} GB",
        "step2_1_title": "PASO 2.1 — VISTA PREVIA RÁPIDA (OPCIONAL)",
        "step2_1_desc": "Si quieres, puedes descargar 4 cuadros de muestra para ver cómo lucirá el mapa antes de iniciar.",
        "btn_fire_test": "VER 4 MUESTRAS DE PRUEBA",
        "fire_testing": "Descargando 4 muestras de vista previa...",
        "fire_ok": "Vista previa lista. Todo funciona correctamente.",
        "btn_back_step1": "< VOLVER AL PASO 1",
        "btn_to_step3": "CONFIRMAR Y PASAR AL PASO 3 (DESCARGA) >>",
        "step3_title": "PASO 3 — DESCARGA Y COMPILACIÓN EN VIVO",
        "btn_go_step4": "PASAR AL PASO 4: GUARDAR EN MEMORIA SD >>",
        "banner_ready_title": "LISTO PARA COMENZAR",
        "banner_ready_sub": "Presiona el botón verde 'INICIAR / CONTINUAR' para empezar la descarga.",
        "banner_paused_title": "⏸  EN PAUSA (PROGRESO ASEGURADO EN DISCO)",
        "banner_paused_sub": "Todo lo descargado ya quedó guardado. Presiona 'INICIAR / CONTINUAR' cuando gustes.",
        "banner_net_title": "⚠  SIN INTERNET — EN PAUSA AUTOMÁTICA",
        "banner_net_sub": "La descarga continuará sola en cuanto regrese la conexión a Internet.",
        "banner_prep_title": "⏳  VERIFICANDO PROGRESO PREVIO — INICIA EN ~{cd}",
        "banner_prep_sub": "Revisando qué archivos ya tienes en disco para descargar únicamente lo que falta...",
        "banner_run_title": "⚡  DESCARGANDO: {name} ({pct:.1f}%)",
        "banner_run_sub": "Tiempo restante aprox.: {eta}  |  No desconectes el disco.",
        "banner_done_title": "✔  ¡DESCARGA Y COMPILACIÓN COMPLETADAS AL 100%!",
        "banner_done_sub": "Presiona el botón azul 'PASAR AL PASO 4' para enviar el mapa y las rutas a tu tarjeta MicroSD.",
        "clock_active": "TIEMPO TRANSCURRIDO",
        "clock_eta": "TIEMPO RESTANTE",
        "clock_speed": "VELOCIDAD ACTUAL",
        "btn_start": "▶ INICIAR / CONTINUAR",
        "btn_pause": "⏸ PAUSAR",
        "btn_stop": "⏹ GUARDAR Y DETENER",
        "dd_threads": "Capacidad del procesador",
        "dd_speed": "Velocidad de descarga",
        "spd_slow": "Tranquila y segura",
        "spd_norm": "Normal recomendada",
        "spd_fast": "Rápida",
        "spd_turbo": "Máxima velocidad segura",
        "th_std": "Uso normal",
        "th_fast": "Uso rápido",
        "th_max": "Potencia máxima",
        "live_strip_lbl": "VISTA EN VIVO DE LOS CUADROS QUE SE ESTÁN GUARDANDO:",
        "witness_strip_lbl": "HISTORIAL DE MUESTRAS DE ESTA SESIÓN:",
        "step4_title": "PASO 4 — PASAR TUS MAPAS Y RUTAS A LA TARJETA MICRO-SD",
        "step4_sub": "Selecciona la letra de tu tarjeta MicroSD (o memoria USB) donde se copiarán las carpetas MAP, SECTORS y ARTERIAL.HWY:",
        "dd_sd_drive": "Tarjeta MicroSD o memoria destino para el reloj",
        "step4_ready_msg": "Listo. Elige abajo cómo quieres enviar tus mapas de la PC hacia la memoria SD seleccionada.",
        "mass_ops_title": "ACCIONES PARA TODOS LOS PAQUETES DE LA LISTA (EN LOTE):",
        "btn_all_merge_keep": "1. COMBINAR TODOS EN LA SD (DEJAR COPIA EN PC)",
        "btn_all_merge_move": "2. COMBINAR TODOS EN LA SD (Y BORRAR DE PC)",
        "btn_all_direct_move": "3. MOVER TODOS SIN COMBINAR (Y BORRAR DE PC)",
        "single_ops_title": "TUS PAQUETES GUARDADOS EN LA PC (PUEDES GESTIONARLOS UNO POR UNO):",
        "no_maps_yet": "No hay paquetes guardados en este disco de la PC. Si los guardaste en otro disco, cámbialo en el Paso 2.",
        "btn_item_resume": "▶ CONTINUAR DESCARGA",
        "btn_item_add_routes": "+ DESCARGAR RUTAS (.HWY)",
        "btn_item_merge_keep": "COMBINAR EN SD (DEJAR EN PC)",
        "btn_item_merge_move": "COMBINAR EN SD (BORRAR DE PC)",
        "btn_item_direct_move": "MOVER SIN COMBINAR (BORRAR DE PC)",
        "btn_item_slim": "BORRAR SOLO Z15-Z20",
        "btn_item_del": "ELIMINAR DE PC",
        "transferring_msg": "Pasando y combinando archivos hacia la memoria SD ({pct:.0f}%)... No retires la memoria.",
        "transfer_done_msg": "✔ ¡Listo! Tus mapas (.QOI) y rutas (.HWY) ya quedaron en la memoria SD. Ya puedes retirarla.",
        "nav_s0": ("PASO 0", "Idioma"),
        "nav_s1": ("PASO 1", "Conectar Teléfono"),
        "nav_s2": ("PASO 2 y 2.1", "Disco Temporal PC"),
        "nav_s3": ("PASO 3", "Descargar Mapa/Rutas"),
        "nav_s4": ("PASO 4", "Pasar a MicroSD"),
        "st_current": "[ PASO ACTUAL ]",
        "st_avail": "[ DISPONIBLE ]",
        "st_locked": "[ OCUPADO ]",
        "st_pending": "[ PENDIENTE ]",
        "lock_toast_busy": "Primero pausa o espera a que termine el proceso actual.",
        "lock_toast_no_order": "Primero envía un mapa desde tu teléfono o abre un archivo .JSON en el Paso 1.",
        "tag_removable": "[MEMORIA EXTRAÍBLE / SD]",
        "tag_local": "[DISCO INTERNO PC]",
        "free_lbl": "Libre",
    },
    "en": {
        "step0_title": "STEP 0 — SELECT YOUR LANGUAGE",
        "step0_sub": "Choose your language to begin. The assistant will guide you step by step.",
        "step1_title": "STEP 1 — CONNECT WITH YOUR PHONE",
        "step1_sub": "As soon as you send your selection from your phone, this screen will advance to Step 2 automatically.",
        "cred_box_title": "CONNECTION DETAILS FOR YOUR PHONE",
        "ip_wifi_lbl": "IP ADDRESS (WI-FI / LOCAL NETWORK):",
        "pin_lbl": "PIN CODE:",
        "ip_usb_lbl": "USB CABLE CONNECTION:",
        "usb_wait": "Activates when you turn on 'USB Tethering' on your phone",
        "opt_a_title": "OPTION A: VIA WI-FI OR HOTSPOT",
        "opt_a_body": "1. Connect your phone and PC to the same Wi-Fi (or phone Hotspot).\n2. Tap 'Send to PC' in the phone app.\n3. This installer will jump to Step 2 automatically.",
        "opt_b_title": "OPTION B: VIA USB CABLE",
        "opt_b_body": "1. Plug your phone into the PC with a USB cable.\n2. Enable 'USB Tethering' in your phone settings.\n3. Tap 'Send to PC' in the app.",
        "opt_c_title": "OPTION C: OPEN SAVED FILE (.JSON)",
        "opt_c_body": "If you saved the order as a file on your computer:",
        "btn_pick_file": "BROWSE .JSON FILE ON PC",
        "waiting_order": "Waiting for you to send the selection from your phone...",
        "order_ready": "Order loaded: {name}  |  Mode: {mode_str}  |  Est. size: {mb:.1f} MB",
        "btn_to_step2": "CONTINUE TO STEP 2: CHOOSE DRIVE >>",
        "btn_to_step4_direct": "GO TO MY SAVED MAPS (STEP 4)",
        "step2_title": "STEP 2 — CHOOSE TEMPORARY PC STORAGE DRIVE",
        "dd_pc_drive": "Computer drive where the map will be prepared (EXOSYS_VAULT)",
        "btn_refresh_drives": "REFRESH DRIVES",
        "space_ok": "Free on PC: {pc_gb:.1f} GB  |  Required space: {req_mb:.1f} MB  [ENOUGH SPACE]",
        "space_low": "Free on PC: {pc_gb:.1f} GB  |  Required space: {req_mb:.1f} MB  [NOT ENOUGH SPACE]",
        "space_idle": "Free on PC: {pc_gb:.1f} GB  |  Free on destination SD drive: {sd_gb:.1f} GB",
        "step2_1_title": "STEP 2.1 — QUICK PREVIEW TEST (OPTIONAL)",
        "step2_1_desc": "Optionally download 4 sample squares to preview how the map will look before starting.",
        "btn_fire_test": "PREVIEW 4 SAMPLE SQUARES",
        "fire_testing": "Downloading 4 preview samples...",
        "fire_ok": "Preview ready. Everything works properly.",
        "btn_back_step1": "< BACK TO STEP 1",
        "btn_to_step3": "CONFIRM & GO TO STEP 3 (DOWNLOAD) >>",
        "step3_title": "STEP 3 — LIVE MAP & ROUTE DOWNLOAD",
        "btn_go_step4": "CONTINUE TO STEP 4: TRANSFER TO SD >>",
        "banner_ready_title": "READY TO START",
        "banner_ready_sub": "Press the green 'START / RESUME' button below to begin downloading.",
        "banner_paused_title": "⏸  PAUSED (PROGRESS SAVED)",
        "banner_paused_sub": "Your progress is safely saved. Press 'START / RESUME' whenever you are ready.",
        "banner_net_title": "⚠  NO INTERNET — AUTO-PAUSED",
        "banner_net_sub": "Download will resume automatically as soon as Internet connection returns.",
        "banner_prep_title": "⏳  CHECKING PREVIOUS PROGRESS — STARTS IN ~{cd}",
        "banner_prep_sub": "Auditing existing files on disk so only missing sectors are downloaded...",
        "banner_run_title": "⚡  DOWNLOADING: {name} ({pct:.1f}%)",
        "banner_run_sub": "Estimated time remaining: {eta}  |  Do not unplug the drive.",
        "banner_done_title": "✔  100% DOWNLOAD COMPLETE!",
        "banner_done_sub": "Press the blue 'CONTINUE TO STEP 4' button to transfer the map and routes to your SD card.",
        "clock_active": "ELAPSED TIME",
        "clock_eta": "TIME REMAINING",
        "clock_speed": "CURRENT SPEED",
        "btn_start": "▶ START / RESUME",
        "btn_pause": "⏸ PAUSE",
        "btn_stop": "⏹ SAVE & STOP",
        "dd_threads": "Processor power",
        "dd_speed": "Download speed",
        "spd_slow": "Calm & safe",
        "spd_norm": "Recommended normal",
        "spd_fast": "Fast",
        "spd_turbo": "Maximum safe speed",
        "th_std": "Standard use",
        "th_fast": "Fast use",
        "th_max": "Maximum power",
        "live_strip_lbl": "LIVE VIEW OF MAP SQUARES BEING SAVED:",
        "witness_strip_lbl": "SAMPLE HISTORY OF THIS SESSION:",
        "step4_title": "STEP 4 — TRANSFER MAPS & ROUTES TO SD CARD",
        "step4_sub": "Select the SD card or drive where you want your maps ready to use:",
        "dd_sd_drive": "Destination SD card or drive",
        "step4_ready_msg": "Choose below how you want to send your saved packages to the SD drive.",
        "mass_ops_title": "BATCH ACTIONS FOR ALL SAVED PACKAGES:",
        "btn_all_merge_keep": "1. MERGE ALL INTO SD (KEEP COPY ON PC)",
        "btn_all_merge_move": "2. MERGE ALL INTO SD (& DELETE FROM PC)",
        "btn_all_direct_move": "3. OVERWRITE ALL TO SD (& DELETE FROM PC)",
        "single_ops_title": "YOUR SAVED PACKAGES ON PC (MANAGE INDIVIDUALLY):",
        "no_maps_yet": "No saved maps waiting on this drive.",
        "btn_item_resume": "▶ RESUME DOWNLOAD",
        "btn_item_add_routes": "+ DOWNLOAD ROUTES (.HWY)",
        "btn_item_merge_keep": "MERGE TO SD (KEEP ON PC)",
        "btn_item_merge_move": "MERGE TO SD (DELETE FROM PC)",
        "btn_item_direct_move": "MOVE & OVERWRITE (DELETE FROM PC)",
        "btn_item_slim": "DELETE Z15-Z20 ONLY",
        "btn_item_del": "DELETE FROM PC",
        "transferring_msg": "Merging and transferring files to SD memory ({pct:.0f}%)... Please wait.",
        "transfer_done_msg": "✔ Done! Your maps (.QOI) and routes (.HWY) are ready on the SD card. You may remove it.",
        "nav_s0": ("STEP 0", "Language"),
        "nav_s1": ("STEP 1", "Connect Phone"),
        "nav_s2": ("STEP 2 & 2.1", "PC Temp Drive"),
        "nav_s3": ("STEP 3", "Download Map/Routes"),
        "nav_s4": ("STEP 4", "Send to SD Card"),
        "st_current": "[ CURRENT STEP ]",
        "st_avail": "[ AVAILABLE ]",
        "st_locked": "[ BUSY ]",
        "st_pending": "[ PENDING ]",
        "lock_toast_busy": "Please pause or wait for the current operation to finish first.",
        "lock_toast_no_order": "First send a map from your phone in Step 1.",
        "tag_removable": "[REMOVABLE SD / USB]",
        "tag_local": "[PC INTERNAL DRIVE]",
        "free_lbl": "Free",
    },
    "zh": {
        "step0_title": "第 0 步 — 选择您的语言",
        "step0_sub": "请选择您的语言以开始使用。向导将一步步引导您完成操作。",
        "step1_title": "第 1 步 — 连接您的手机",
        "step1_sub": "当您在手机上发送选定区域后，此画面将自动进入第 2 步。",
        "cred_box_title": "手机连接信息",
        "ip_wifi_lbl": "IP 地址 (无线局域网):",
        "pin_lbl": "安全码 (PIN):",
        "ip_usb_lbl": "USB 数据线连接:",
        "usb_wait": "在手机设置中开启“USB 网络共享”后自动激活",
        "opt_a_title": "方式 A：通过 Wi-Fi 或手机热点",
        "opt_a_body": "1. 将手机和电脑连接到同一个 Wi-Fi（或手机热点）。\n2. 在手机应用中点击“发送到电脑”。\n3. 程序将自动跳转到第 2 步。",
        "opt_b_title": "方式 B：通过 USB 数据线",
        "opt_b_body": "1. 用 USB 数据线将手机连接到电脑。\n2. 在手机设置中打开“USB 网络共享”。\n3. 在手机应用中点击“发送到电脑”。",
        "opt_c_title": "方式 C：打开电脑上的文件 (.JSON)",
        "opt_c_body": "如果您已将订单保存为文件：",
        "btn_pick_file": "在电脑上选择文件",
        "waiting_order": "正在等待从手机发送地图选择...",
        "order_ready": "已收到地图任务: {name}  |  模式: {mode_str}  |  预计大小: {mb:.1f} MB",
        "btn_to_step2": "继续前往第 2 步：选择磁盘 >>",
        "btn_to_step4_direct": "直接管理已保存的地图 (第 4 步)",
        "step2_title": "第 2 步 — 选择电脑临时存储位置",
        "dd_pc_drive": "用于临时存放地图的电脑磁盘",
        "btn_refresh_drives": "刷新磁盘列表",
        "space_ok": "电脑可用空间: {pc_gb:.1f} GB  |  所需空间: {req_mb:.1f} MB  [空间充足]",
        "space_low": "电脑可用空间: {pc_gb:.1f} GB  |  所需空间: {req_mb:.1f} MB  [空间不足]",
        "space_idle": "电脑可用空间: {pc_gb:.1f} GB  |  目标存储卡可用空间: {sd_gb:.1f} GB",
        "step2_1_title": "第 2.1 步 — 快速预览测试（可选）",
        "step2_1_desc": "您可以先下载 4 张预览图，确认地图效果良好后再开始正式下载。",
        "btn_fire_test": "测试下载 4 张预览图",
        "fire_testing": "正在下载 4 张预览图...",
        "fire_ok": "预览完成，连接与画质完全正常。",
        "btn_back_step1": "< 返回第 1 步",
        "btn_to_step3": "确认磁盘并进入第 3 步 (开始下载) >>",
        "step3_title": "第 3 步 — 正在下载地图与路线",
        "btn_go_step4": "继续前往第 4 步：写入存储卡 >>",
        "banner_ready_title": "准备就绪",
        "banner_ready_sub": "点击下方的绿色按钮“开始 / 继续”启动下载。",
        "banner_paused_title": "⏸  已暂停",
        "banner_paused_sub": "当前进度已安全保存。您可以随时点击“开始 / 继续”恢复下载。",
        "banner_net_title": "⚠  网络中断 — 已自动暂停",
        "banner_net_sub": "网络恢复后将自动继续下载。",
        "banner_prep_title": "⏳  正在准备下载 — 约 {cd} 后开始",
        "banner_prep_sub": "正在整理路线与地图网格...",
        "banner_run_title": "⚡  正在下载: {name} ({pct:.1f}%)",
        "banner_run_sub": "预计剩余时间: {eta}  |  请勿拔出磁盘。",
        "banner_done_title": "✔  100% 下载完成！",
        "banner_done_sub": "请点击蓝色按钮“继续前往第 4 步”，将地图融合或移入存储卡。",
        "clock_active": "已用时间",
        "clock_eta": "预计剩余时间",
        "clock_speed": "当前下载速度",
        "btn_start": "▶ 开始 / 继续",
        "btn_pause": "⏸ 暂停",
        "btn_stop": "⏹ 保存并停止",
        "dd_threads": "处理器性能模式",
        "dd_speed": "下载速度调节",
        "spd_slow": "平稳安全",
        "spd_norm": "标准推荐",
        "spd_fast": "高速模式",
        "spd_turbo": "极速安全模式",
        "th_std": "标准模式",
        "th_fast": "快速模式",
        "th_max": "全速模式",
        "live_strip_lbl": "实时保存的地图画面预览：",
        "witness_strip_lbl": "本次下载进度抽样记录：",
        "step4_title": "第 4 步 — 将地图与路线写入存储卡",
        "step4_sub": "请选择您要使用的存储卡或目标磁盘：",
        "dd_sd_drive": "用于手表的存储卡或目标磁盘",
        "step4_ready_msg": "请在下方选择您希望如何合并或移动已保存的地图。",
        "mass_ops_title": "对所有已保存地图执行操作：",
        "btn_all_merge_keep": "1. 全部合并到存储卡（在电脑保留备份）",
        "btn_all_merge_move": "2. 全部合并到存储卡（并从电脑删除）",
        "btn_all_direct_move": "3. 直接覆盖移动到存储卡（并从电脑删除）",
        "single_ops_title": "单独管理每个地图包：",
        "no_maps_yet": "当前磁盘没有已保存的地图。",
        "btn_item_resume": "▶ 继续下载",
        "btn_item_add_routes": "+ 下载路线 (.HWY)",
        "btn_item_merge_keep": "合并到存储卡 (保留电脑备份)",
        "btn_item_merge_move": "合并到存储卡 (从电脑删除)",
        "btn_item_direct_move": "直接移动到存储卡 (从电脑删除)",
        "btn_item_slim": "删除 Z15-Z20",
        "btn_item_del": "从电脑删除",
        "transferring_msg": "正在将地图与路线写入存储卡 ({pct:.0f}%)... 请稍候。",
        "transfer_done_msg": "✔ 操作完成！您的地图与路线已写入存储卡，现在可以安全拔出。",
        "nav_s0": ("第 0 步", "语言选择"),
        "nav_s1": ("第 1 步", "连接手机"),
        "nav_s2": ("第 2 & 2.1 步", "选择磁盘"),
        "nav_s3": ("第 3 步", "下载地图"),
        "nav_s4": ("第 4 步", "写入存储卡"),
        "st_current": "[ 当前步骤 ]",
        "st_avail": "[ 可进入 ]",
        "st_locked": "[ 正在运行 ]",
        "st_pending": "[ 等待中 ]",
        "lock_toast_busy": "请先暂停或等待当前任务完成后再切换步骤。",
        "lock_toast_no_order": "请先在第 1 步从手机发送地图任务。",
        "tag_removable": "[可移动存储卡]",
        "tag_local": "[电脑本地磁盘]",
        "free_lbl": "可用",
    },
    "ja": {
        "step0_title": "ステップ 0 — 言語を選択してください",
        "step0_sub": "使用する言語を選んでください。順番にわかりやすく案内します。",
        "step1_title": "ステップ 1 — スマートフォンと接続",
        "step1_sub": "スマホから範囲を送信すると、自動的にステップ 2 へ進みます。",
        "cred_box_title": "スマホアプリに入力する接続情報",
        "ip_wifi_lbl": "IPアドレス (Wi-Fi / 同じネットワーク):",
        "pin_lbl": "PINコード:",
        "ip_usb_lbl": "USBケーブル接続:",
        "usb_wait": "スマホの「USBテザリング」をオンにすると有効になります",
        "opt_a_title": "方法 A：Wi-Fi またはテザリング",
        "opt_a_body": "1. スマホとPCを同じWi-Fi（またはスマホのテザリング）に繋ぎます。\n2. スマホアプリの「PCへ送信」を押します。\n3. 自動的にステップ 2 へ進みます。",
        "opt_b_title": "方法 B：USBケーブル接続",
        "opt_b_body": "1. スマホとPCをUSBケーブルで繋ぎます。\n2. スマホの設定で「USBテザリング」をオンにします。\n3. アプリで「PCへ送信」を押します。",
        "opt_c_title": "方法 C：保存したファイルを開く (.JSON)",
        "opt_c_body": "PCに保存したファイルから読み込む場合：",
        "btn_pick_file": "PC内のファイルを選択",
        "waiting_order": "スマホからのデータ送信を待っています...",
        "order_ready": "受信完了: {name}  |  モード: {mode_str}  |  予想サイズ: {mb:.1f} MB",
        "btn_to_step2": "ステップ 2（保存先の選択）へ進む >>",
        "btn_to_step4_direct": "保存済みマップ一覧へ (ステップ 4)",
        "step2_title": "ステップ 2 — 一時保存するドライブの選択",
        "dd_pc_drive": "このPC内で一時的に作業を行うドライブ",
        "btn_refresh_drives": "ドライブを更新",
        "space_ok": "PC空き容量: {pc_gb:.1f} GB  |  必要容量: {req_mb:.1f} MB  [容量OK]",
        "space_low": "PC空き容量: {pc_gb:.1f} GB  |  必要容量: {req_mb:.1f} MB  [容量不足]",
        "space_idle": "PC空き容量: {pc_gb:.1f} GB  |  カード空き容量: {sd_gb:.1f} GB",
        "step2_1_title": "ステップ 2.1 — 事前プレビュー確認（任意）",
        "step2_1_desc": "本番ダウンロードの前に、サンプル4枚を表示して見た目を確認できます。",
        "btn_fire_test": "サンプル4枚をテスト表示",
        "fire_testing": "サンプルをダウンロード中...",
        "fire_ok": "プレビュー成功！正常にダウンロードできます。",
        "btn_back_step1": "< ステップ 1 に戻る",
        "btn_to_step3": "確認してステップ 3（ダウンロード）へ >>",
        "step3_title": "ステップ 3 — マップとルートのダウンロード",
        "btn_go_step4": "ステップ 4（SDカードへ転送）へ進む >>",
        "banner_ready_title": "開始準備完了",
        "banner_ready_sub": "緑色の「開始 / 再開」ボタンを押すとダウンロードが始まります。",
        "banner_paused_title": "⏸  一時停止中",
        "banner_paused_sub": "ここまでの進捗は保存されています。「開始 / 再開」でいつでも続けられます。",
        "banner_net_title": "⚠  通信待機中 — 自動一時停止",
        "banner_net_sub": "インターネット接続が戻り次第、自動で再開します。",
        "banner_prep_title": "⏳  準備中 — あと約 {cd} で開始します",
        "banner_prep_sub": "ルートと地図データを整理しています...",
        "banner_run_title": "⚡  ダウンロード中: {name} ({pct:.1f}%)",
        "banner_run_sub": "残り時間の目安: {eta}  |  ドライブを抜かないでください。",
        "banner_done_title": "✔  100% ダウンロード完了！",
        "banner_done_sub": "青い「ステップ 4 へ進む」ボタンを押してメモリーカードへ転送してください。",
        "clock_active": "経過時間",
        "clock_eta": "残り時間",
        "clock_speed": "現在の速度",
        "btn_start": "▶ 開始 / 再開",
        "btn_pause": "⏸ 一時停止",
        "btn_stop": "⏹ 保存して終了",
        "dd_threads": "PCの処理パワー",
        "dd_speed": "ダウンロード速度",
        "spd_slow": "安全・ゆっくり",
        "spd_norm": "標準（おすすめ）",
        "spd_fast": "高速",
        "spd_turbo": "最速・安全モード",
        "th_std": "標準",
        "th_fast": "高速",
        "th_max": "最大パワー",
        "live_strip_lbl": "リアルタイム保存プレビュー：",
        "witness_strip_lbl": "このセッションの履歴サンプル：",
        "step4_title": "ステップ 4 — メモリーカードへ統合・移動",
        "step4_sub": "マップを入れるメモリーカード（またはドライブ）を選んでください：",
        "dd_sd_drive": "転送先のメモリーカード / ドライブ",
        "step4_ready_msg": "既存のマップと統合するか、そのまま移動するかを下から選んでください。",
        "mass_ops_title": "保存済みマップすべてを一括処理：",
        "btn_all_merge_keep": "1. すべてSDに統合（PCにも残す）",
        "btn_all_merge_move": "2. すべてSDに統合（PCから削除して容量を空ける）",
        "btn_all_direct_move": "3. すべてSDへ上書き移動（PCから削除）",
        "single_ops_title": "個別のマップごとに操作：",
        "no_maps_yet": "このドライブに保存されているマップはまだありません。",
        "btn_item_resume": "▶ 続きをダウンロード",
        "btn_item_add_routes": "+ ルートを取得 (.HWY)",
        "btn_item_merge_keep": "SDに統合 (PCに残す)",
        "btn_item_merge_move": "SDに統合 (PCから削除)",
        "btn_item_direct_move": "上書き移動 (PCから削除)",
        "btn_item_slim": "Z15-Z20のみ削除",
        "btn_item_del": "PCから削除",
        "transferring_msg": "メモリーカードへ書き込み中 ({pct:.0f}%)... お待ちください。",
        "transfer_done_msg": "✔ 完了しました！マップとルートがSDカードに保存されました。",
        "nav_s0": ("ステップ 0", "言語選択"),
        "nav_s1": ("ステップ 1", "スマホ接続"),
        "nav_s2": ("ステップ 2", "ドライブ選択"),
        "nav_s3": ("ステップ 3", "ダウンロード"),
        "nav_s4": ("ステップ 4", "SDへ転送"),
        "st_current": "[ 現在のステップ ]",
        "st_avail": "[ 選択可能 ]",
        "st_locked": "[ 処理中ロック ]",
        "st_pending": "[ 未完了 ]",
        "lock_toast_busy": "安全のため、一時停止するか処理が終わるまでお待ちください。",
        "lock_toast_no_order": "先にステップ 1 でスマホからマップを送信してください。",
        "tag_removable": "[メモリーカード]",
        "tag_local": "[PC内蔵ドライブ]",
        "free_lbl": "空き",
    },
    "hi": {
        "step0_title": "चरण 0 — अपनी भाषा चुनें",
        "step0_sub": "शुरू करने के लिए अपनी भाषा चुनें। यह प्रोग्राम आपको हर कदम पर आसान रास्ता दिखाएगा।",
        "step1_title": "चरण 1 — अपने फ़ोन से जोड़ें",
        "step1_sub": "जैसे ही आप फ़ोन से नक्शा भेजेंगे, यह स्क्रीन अपने-आप चरण 2 पर चली जाएगी।",
        "cred_box_title": "फ़ोन में डालने के लिए कनेक्शन जानकारी",
        "ip_wifi_lbl": "IP पता (Wi-Fi / नेटवर्क):",
        "pin_lbl": "पिन कोड (PIN):",
        "ip_usb_lbl": "USB केबल कनेक्शन:",
        "usb_wait": "फ़ोन में 'USB Tethering' चालू करने पर यह काम करेगा",
        "opt_a_title": "विकल्प A: Wi-Fi या हॉटस्पॉट द्वारा",
        "opt_a_body": "1. अपने फ़ोन और PC को एक ही Wi-Fi (या फ़ोन हॉटस्पॉट) से जोड़ें।\n2. फ़ोन ऐप में 'Send to PC' दबाएँ।\n3. यह अपने-आप चरण 2 पर चला जाएगा।",
        "opt_b_title": "विकल्प B: USB केबल द्वारा",
        "opt_b_body": "1. फ़ोन को USB केबल से कंप्यूटर से जोड़ें।\n2. फ़ोन की सेटिंग में 'USB Tethering' चालू करें।\n3. ऐप में 'Send to PC' दबाएँ।",
        "opt_c_title": "विकल्प C: कंप्यूटर से फ़ाइल खोलें (.JSON)",
        "opt_c_body": "यदि आपने फ़ाइल कंप्यूटर में सेव की है:",
        "btn_pick_file": "कंप्यूटर से फ़ाइल चुनें",
        "waiting_order": "फ़ोन से नक्शे का आदेश मिलने की प्रतीक्षा हो रही है...",
        "order_ready": "आदेश प्राप्त हुआ: {name}  |  मोड: {mode_str}  |  आकार: {mb:.1f} MB",
        "btn_to_step2": "चरण 2 पर जाएँ: डिस्क चुनें >>",
        "btn_to_step4_direct": "मेरे सेव किए गए नक्शे देखें (चरण 4)",
        "step2_title": "चरण 2 — कंप्यूटर की डिस्क चुनें",
        "dd_pc_drive": "कंप्यूटर की वह डिस्क जहाँ नक्शा तैयार किया जाएगा",
        "btn_refresh_drives": "डिस्क सूची ताज़ा करें",
        "space_ok": "PC में खाली जगह: {pc_gb:.1f} GB  |  ज़रूरी जगह: {req_mb:.1f} MB  [पर्याप्त जगह है]",
        "space_low": "PC में खाली जगह: {pc_gb:.1f} GB  |  ज़रूरी जगह: {req_mb:.1f} MB  [जगह कम है]",
        "space_idle": "PC में खाली जगह: {pc_gb:.1f} GB  |  मेमोरी कार्ड में खाली जगह: {sd_gb:.1f} GB",
        "step2_1_title": "चरण 2.1 — छोटा परीक्षण (ऐच्छिक)",
        "step2_1_desc": "पूरा नक्शा डाउनलोड करने से पहले आप 4 नमूने देखकर जाँच सकते हैं।",
        "btn_fire_test": "4 नमूने डाउनलोड करके देखें",
        "fire_testing": "4 नमूने डाउनलोड हो रहे हैं...",
        "fire_ok": "परीक्षण सफल! सब कुछ सही काम कर रहा है।",
        "btn_back_step1": "< चरण 1 पर वापस जाएँ",
        "btn_to_step3": "पुष्टि करें और चरण 3 (डाउनलोड) पर जाएँ >>",
        "step3_title": "चरण 3 — नक्शा और मार्ग डाउनलोड",
        "btn_go_step4": "चरण 4 पर जाएँ: मेमोरी कार्ड में भेजें >>",
        "banner_ready_title": "शुरू करने के लिए तैयार",
        "banner_ready_sub": "डाउनलोड शुरू करने के लिए नीचे हरा बटन 'शुरू करें / आगे बढ़ाएँ' दबाएँ।",
        "banner_paused_title": "⏸  रुका हुआ है (PAUSED)",
        "banner_paused_sub": "आपका काम सुरक्षित है। आगे बढ़ाने के लिए हरा बटन दबाएँ।",
        "banner_net_title": "⚠  इंटरनेट नहीं है — अपने-आप रुका",
        "banner_net_sub": "इंटरनेट वापस आते ही डाउनलोड अपने-आप शुरू हो जाएगा।",
        "banner_prep_title": "⏳  तैयारी हो रही है — ~{cd} में शुरू होगा",
        "banner_prep_sub": "रास्ते और नक्शे व्यवस्थित किए जा रहे हैं...",
        "banner_run_title": "⚡  डाउनलोड हो रहा है: {name} ({pct:.1f}%)",
        "banner_run_sub": "अनुमानित शेष समय: {eta}  |  कृपया डिस्क न निकालें।",
        "banner_done_title": "✔  100% डाउनलोड पूरा हुआ!",
        "banner_done_sub": "नक्शे को मेमोरी कार्ड में भेजने के लिए नीला बटन 'चरण 4 पर जाएँ' दबाएँ।",
        "clock_active": "कुल समय",
        "clock_eta": "शेष समय",
        "clock_speed": "डाउनलोड गति",
        "btn_start": "▶ शुरू करें / आगे बढ़ाएँ",
        "btn_pause": "⏸ रोकें (PAUSE)",
        "btn_stop": "⏹ सेव करें और बंद करें",
        "dd_threads": "कंप्यूटर क्षमता",
        "dd_speed": "डाउनलोड की गति",
        "spd_slow": "धीमी और सुरक्षित",
        "spd_norm": "सामान्य (सुझाई गई)",
        "spd_fast": "तेज़",
        "spd_turbo": "अधिकतम सुरक्षित गति",
        "th_std": "सामान्य",
        "th_fast": "तेज़",
        "th_max": "पूर्ण क्षमता",
        "live_strip_lbl": "अभी सेव हो रहे नक्शे की झलक:",
        "witness_strip_lbl": "इस सत्र के नमूने:",
        "step4_title": "चरण 4 — नक्शों को मेमोरी कार्ड में मिलाएँ या भेजें",
        "step4_sub": "अपना मेमोरी कार्ड या डिस्क चुनें जहाँ आप नक्शे रखना चाहते हैं:",
        "dd_sd_drive": "मेमोरी कार्ड या लक्ष्य डिस्क",
        "step4_ready_msg": "नीचे चुनें कि आप नक्शों को मेमोरी कार्ड में मिलाना चाहते हैं या सीधे भेजना चाहते हैं।",
        "mass_ops_title": "सभी सेव किए गए नक्शों के लिए विकल्प:",
        "btn_all_merge_keep": "1. सभी को SD में मिलाएँ (PC में भी कॉपी रखें)",
        "btn_all_merge_move": "2. सभी को SD में मिलाएँ (और PC से हटाएँ)",
        "btn_all_direct_move": "3. सीधे SD में भेजें (और PC से हटाएँ)",
        "single_ops_title": "एक-एक करके नक्शे प्रबंधित करें:",
        "no_maps_yet": "इस डिस्क पर अभी कोई नक्शा सेव नहीं है।",
        "btn_item_resume": "▶ डाउनलोड पूरा करें",
        "btn_item_add_routes": "+ मार्ग डाउनलोड करें (.HWY)",
        "btn_item_merge_keep": "SD में मिलाएँ (PC में रखें)",
        "btn_item_merge_move": "SD में मिलाएँ (PC से हटाएँ)",
        "btn_item_direct_move": "सीधे भेजें (PC से हटाएँ)",
        "btn_item_slim": "Z15-Z20 हटाएँ",
        "btn_item_del": "PC से हटाएँ",
        "transferring_msg": "मेमोरी कार्ड में नक्शे भेजे जा रहे हैं ({pct:.0f}%)... कृपया प्रतीक्षा करें।",
        "transfer_done_msg": "✔ पूरा हुआ! आपके नक्शे और मार्ग मेमोरी कार्ड में तैयार हैं।",
        "nav_s0": ("चरण 0", "भाषा (Language)"),
        "nav_s1": ("चरण 1", "फ़ोन जोड़ें"),
        "nav_s2": ("चरण 2", "डिस्क चुनें"),
        "nav_s3": ("चरण 3", "डाउनलोड"),
        "nav_s4": ("चरण 4", "SD में भेजें"),
        "st_current": "[ वर्तमान चरण ]",
        "st_avail": "[ उपलब्ध ]",
        "st_locked": "[ कार्य चालू है ]",
        "st_pending": "[ बाकी है ]",
        "lock_toast_busy": "कृपया पहले रोकें या चल रहे काम के पूरा होने की प्रतीक्षा करें।",
        "lock_toast_no_order": "पहले चरण 1 में अपने फ़ोन से नक्शा भेजें।",
        "tag_removable": "[मेमोरी कार्ड / USB]",
        "tag_local": "[कंप्यूटर डिस्क]",
        "free_lbl": "खाली",
    },
    "fr": {
        "step0_title": "ÉTAPE 0 — CHOISISSEZ VOTRE LANGUE",
        "step0_sub": "Sélectionnez votre langue pour commencer. L'assistant vous guidera étape par étape.",
        "step1_title": "ÉTAPE 1 — CONNEXION AVEC VOTRE TÉLÉPHONE",
        "step1_sub": "Dès que vous envoyez votre sélection depuis le téléphone, cet écran passera seul à l'Étape 2.",
        "cred_box_title": "INFORMATIONS DE CONNEXION POUR VOTRE TÉLÉPHONE",
        "ip_wifi_lbl": "ADRESSE IP (WI-FI / RÉSEAU LOCAL) :",
        "pin_lbl": "CODE PIN :",
        "ip_usb_lbl": "CONNEXION PAR CÂBLE USB :",
        "usb_wait": "S'active en allumant le 'Partage de connexion USB' sur votre téléphone",
        "opt_a_title": "OPTION A : PAR WI-FI OU POINT D'ACCÈS",
        "opt_a_body": "1. Connectez votre téléphone et ce PC au même Wi-Fi (ou au point d'accès du téléphone).\n2. Touchez 'Envoyer au PC' dans l'application.\n3. Le programme passera automatiquement à l'Étape 2.",
        "opt_b_title": "OPTION B : PAR CÂBLE USB",
        "opt_b_body": "1. Branchez votre téléphone au PC avec un câble USB.\n2. Activez le 'Partage de connexion USB' dans les réglages du téléphone.\n3. Touchez 'Envoyer au PC'.",
        "opt_c_title": "OPTION C : OUVRIR UN FICHIER ENREGISTRÉ (.JSON)",
        "opt_c_body": "Si vous avez enregistré la commande sous forme de fichier :",
        "btn_pick_file": "CHOISIR UN FICHIER SUR LE PC",
        "waiting_order": "En attente de l'envoi depuis votre téléphone...",
        "order_ready": "Commande reçue : {name}  |  Mode: {mode_str}  |  Taille estimée : {mb:.1f} MB",
        "btn_to_step2": "CONTINUER VERS L'ÉTAPE 2 : CHOISIR LE DISQUE >>",
        "btn_to_step4_direct": "ALLER À MES CARTES ENREGISTRÉES (ÉTAPE 4)",
        "step2_title": "ÉTAPE 2 — CHOISIR LE DISQUE TEMPORAIRE",
        "dd_pc_drive": "Disque de cet ordinateur où la carte sera préparée",
        "btn_refresh_drives": "ACTUALISER LES DISQUES",
        "space_ok": "Espace libre PC : {pc_gb:.1f} GB  |  Requis : {req_mb:.1f} MB  [ESPACE SUFFISANT]",
        "space_low": "Espace libre PC : {pc_gb:.1f} GB  |  Requis : {req_mb:.1f} MB  [ESPACE INSUFFISANT]",
        "space_idle": "Espace libre PC : {pc_gb:.1f} GB  |  Espace libre carte mémoire : {sd_gb:.1f} GB",
        "step2_1_title": "ÉTAPE 2.1 — APERÇU RAPIDE (OPTIONNEL)",
        "step2_1_desc": "Vous pouvez télécharger 4 carrés d'essai pour vérifier le rendu visuel avant de lancer.",
        "btn_fire_test": "VOIR 4 ÉCHANTILLONS D'ESSAI",
        "fire_testing": "Téléchargement de 4 échantillons d'aperçu...",
        "fire_ok": "Aperçu prêt. Tout fonctionne parfaitement.",
        "btn_back_step1": "< RETOUR À L'ÉTAPE 1",
        "btn_to_step3": "CONFIRMER ET PASSER À L'ÉTAPE 3 (TÉLÉCHARGEMENT) >>",
        "step3_title": "ÉTAPE 3 — TÉLÉCHARGEMENT DE LA CARTE",
        "btn_go_step4": "CONTINUER VERS L'ÉTAPE 4 : FUSIONNER OU DÉPLACER >>",
        "banner_ready_title": "PRÊT À DÉMARRER",
        "banner_ready_sub": "Appuyez sur le bouton vert 'DÉMARRER / REPRENDRE' ci-dessous pour commencer.",
        "banner_paused_title": "⏸  EN PAUSE",
        "banner_paused_sub": "Votre progression est sauvegardée. Appuyez sur 'DÉMARRER / REPRENDRE' pour continuer.",
        "banner_net_title": "⚠  PAS D'INTERNET — PAUSE AUTOMATIQUE",
        "banner_net_sub": "Le téléchargement reprendra tout seul dès le retour de la connexion.",
        "banner_prep_title": "⏳  PRÉPARATION — DÉMARRE DANS ~{cd}",
        "banner_prep_sub": "Organisation des routes et de la carte en cours...",
        "banner_run_title": "⚡  TÉLÉCHARGEMENT : {name} ({pct:.1f}%)",
        "banner_run_sub": "Temps restant estimé : {eta}  |  Ne débranchez pas le disque.",
        "banner_done_title": "✔  TÉLÉCHARGEMENT TERMINÉ À 100 % !",
        "banner_done_sub": "Appuyez sur le bouton bleu 'CONTINUER VERS L'ÉTAPE 4' pour fusionner ou déplacer la carte.",
        "clock_active": "TEMPS ÉCOULÉ",
        "clock_eta": "TEMPS RESTANT",
        "clock_speed": "VITESSE ACTUELLE",
        "btn_start": "▶ DÉMARRER / REPRENDRE",
        "btn_pause": "⏸ PAUSE",
        "btn_stop": "⏹ SAUVEGARDER & ARRÊTER",
        "dd_threads": "Puissance du processeur",
        "dd_speed": "Vitesse de téléchargement",
        "spd_slow": "Calme et sûre",
        "spd_norm": "Normale recommandée",
        "spd_fast": "Rapide",
        "spd_turbo": "Vitesse maximale sûre",
        "th_std": "Usage standard",
        "th_fast": "Usage rapide",
        "th_max": "Puissance maximale",
        "live_strip_lbl": "APERÇU EN DIRECT DES ZONES ENREGISTRÉES :",
        "witness_strip_lbl": "HISTORIQUE DES ÉCHANTILLONS DE LA SESSION :",
        "step4_title": "ÉTAPE 4 — FUSIONNER OU DÉPLACER VOS CARTES SUR LA MÉMOIRE",
        "step4_sub": "Choisissez la carte mémoire ou le disque où placer vos cartes prêtes à l'emploi :",
        "dd_sd_drive": "Carte mémoire ou disque de destination",
        "step4_ready_msg": "Choisissez ci-dessous si vous souhaitez fusionner vos cartes ou les déplacer directement.",
        "mass_ops_title": "ACTIONS POUR TOUTES VOS CARTES ENREGISTRÉES :",
        "btn_all_merge_keep": "1. TOUT FUSIONNER SUR LA MÉMOIRE (GARDER COPIE SUR PC)",
        "btn_all_merge_move": "2. TOUT FUSIONNER ET DÉPLACER (LIBÉRER ESPACE PC)",
        "btn_all_direct_move": "3. DÉPLACER TOUT DIRECTEMENT SUR LA MÉMOIRE",
        "single_ops_title": "VOS CARTES ENREGISTRÉES (GESTION INDIVIDUELLE) :",
        "no_maps_yet": "Aucune carte enregistrée sur ce disque.",
        "btn_item_resume": "▶ REPRENDRE",
        "btn_item_add_routes": "+ TÉLÉCHARGER ROUTES (.HWY)",
        "btn_item_merge_keep": "FUSIONNER (GARDER COPIE)",
        "btn_item_merge_move": "FUSIONNER ET DÉPLACER",
        "btn_item_direct_move": "DÉPLACER SEULEMENT",
        "btn_item_slim": "ALLÉGER",
        "btn_item_del": "SUPPRIMER",
        "transferring_msg": "Fusion et transfert vers la carte mémoire ({pct:.0f}%)... Veuillez patienter.",
        "transfer_done_msg": "Terminé ! Vos cartes sont fusionnées sur la mémoire sélectionnée. Vous pouvez la retirer.",
        "nav_s0": ("ÉTAPE 0", "Langue"),
        "nav_s1": ("ÉTAPE 1", "Connexion"),
        "nav_s2": ("ÉTAPE 2 & 2.1", "Disque"),
        "nav_s3": ("ÉTAPE 3", "Télécharger"),
        "nav_s4": ("ÉTAPE 4", "Fusionner / Déplacer"),
        "st_current": "[ ÉTAPE ACTUELLE ]",
        "st_avail": "[ DISPONIBLE ]",
        "st_locked": "[ EN COURS ]",
        "st_pending": "[ EN ATTENTE ]",
        "lock_toast_busy": "Veuillez mettre en pause ou attendre la fin de l'opération en cours.",
        "lock_toast_no_order": "Envoyez d'abord une carte depuis votre téléphone à l'Étape 1.",
        "tag_removable": "[CARTE MÉMOIRE / USB]",
        "tag_local": "[DISQUE PC]",
        "free_lbl": "Libre",
    },
    "ar": {
        "step0_title": "الخطوة 0 — اختر لغتك",
        "step0_sub": "اختر لغتك للبدء. سيرشدك المساعد خطوة بخطوة بسهولة.",
        "step1_title": "الخطوة 1 — التوصيل بهاتفك",
        "step1_sub": "بمجرد إرسال التحديد من هاتفك، ستنتقل هذه النافذة تلقائياً إلى الخطوة 2.",
        "cred_box_title": "بيانات الاتصال להاتفك",
        "ip_wifi_lbl": "عنوان IP (واي فاي / الشبكة):",
        "pin_lbl": "رمز PIN:",
        "ip_usb_lbl": "الاتصال عبر كابل USB:",
        "usb_wait": "يتفعل عند تشغيل 'تقييد USB' في إعدادات هاتفك",
        "opt_a_title": "الخيار أ: عبر الواي فاي أو نقطة الاتصال",
        "opt_a_body": "1. وصّل هاتفك والكمبيوتر بنفس شبكة الواي فاي.\n2. اضغط على 'إرسال إلى الكمبيوتر' في تطبيق الهاتف.\n3. سينتقل البرنامج تلقائياً إلى الخطوة 2.",
        "opt_b_title": "الخيار ب: عبر كابل USB",
        "opt_b_body": "1. وصّل هاتفك بالكمبيوتر عبر كابل USB.\n2. فعّل 'تقييد USB' من إعدادات الهاتف.\n3. اضغط على 'إرسال إلى الكمبيوتر' في التطبيق.",
        "opt_c_title": "الخيار ج: فتح ملف محفوظ (.JSON)",
        "opt_c_body": "إذا قمت بحفظ الطلب كملف على جهاز الكمبيوتر:",
        "btn_pick_file": "اختيار ملف من الكمبيوتر",
        "waiting_order": "في انتظار إرسال الخريطة من هاتفك...",
        "order_ready": "تم استلام الطلب: {name}  |  الوضع: {mode_str}  |  الحجم التقريبي: {mb:.1f} MB",
        "btn_to_step2": "المتابعة إلى الخطوة 2: اختيار القرص >>",
        "btn_to_step4_direct": "الذهاب إلى خرائطي المحفوظة (الخطوة 4)",
        "step2_title": "الخطوة 2 — اختيار قرص الحفظ المؤقت",
        "dd_pc_drive": "قرص الكمبيوتر الذي سيتم تجهيز الخريطة فيه",
        "btn_refresh_drives": "تحديث الأقراص",
        "space_ok": "المساحة المتاحة: {pc_gb:.1f} GB  |  المطلوبة: {req_mb:.1f} MB  [المساحة كافية]",
        "space_low": "المساحة المتاحة: {pc_gb:.1f} GB  |  المطلوبة: {req_mb:.1f} MB  [المساحة غير كافية]",
        "space_idle": "المتاح في الكمبيوتر: {pc_gb:.1f} GB  |  المتاح في الذاكرة: {sd_gb:.1f} GB",
        "step2_1_title": "الخطوة 2.1 — معاينة سريعة (اختياري)",
        "step2_1_desc": "يمكنك تحميل 4 عينات تجريبية لرؤية شكل الخريطة قبل البدء.",
        "btn_fire_test": "عرض 4 عينات تجريبية",
        "fire_testing": "جارٍ تحميل 4 عينات للمعاينة...",
        "fire_ok": "المعاينة جاهزة. كل شيء يعمل بشكل ممتاز.",
        "btn_back_step1": "< العودة للخطوة 1",
        "btn_to_step3": "تأكيد والانتقال للخطوة 3 (التحميل) >>",
        "step3_title": "الخطوة 3 — تحميل الخريطة",
        "btn_go_step4": "المتابعة للخطوة 4: صهر (دمج) أو نقل للذاكرة >>",
        "banner_ready_title": "جاهز للبدء",
        "banner_ready_sub": "اضغط على الزر الأخضر 'بدء / متابعة' بالأسفل لبدء التحميل.",
        "banner_paused_title": "⏸  متوقف مؤقتاً",
        "banner_paused_sub": "تم حفظ تقدمك بأمان. اضغط 'بدء / متابعة' في أي وقت للاستمرار.",
        "banner_net_title": "⚠  لا يوجد اتصال بالإنترنت — توقف تلقائي",
        "banner_net_sub": "سيُستأنف التحميل تلقائياً فور عودة الاتصال بالإنترنت.",
        "banner_prep_title": "⏳  جارٍ التجهيز — يبدأ خلال ~{cd}",
        "banner_prep_sub": "جارٍ تنظيم الخريطة والمسارات قبل التحميل...",
        "banner_run_title": "⚡  جارٍ التحميل: {name} ({pct:.1f}%)",
        "banner_run_sub": "الوقت المتبقي التقريبي: {eta}  |  لا تفصل القرص.",
        "banner_done_title": "✔  اكتمل التحميل بنسبة 100%!",
        "banner_done_sub": "اضغط على الزر الأزرق 'المتابعة للخطوة 4' لصهر أو نقل الخريطة إلى بطاقة الذاكرة.",
        "clock_active": "الوقت المنقضي",
        "clock_eta": "الوقت المتبقي",
        "clock_speed": "السرعة الحالية",
        "btn_start": "▶ بدء / متابعة",
        "btn_pause": "⏸ إيقاف مؤقت",
        "btn_stop": "⏹ حفظ وإغلاق",
        "dd_threads": "قوة المعالج",
        "dd_speed": "سرعة التحميل",
        "spd_slow": "هادئة وآمنة",
        "spd_norm": "عادية موصى بها",
        "spd_fast": "سريعة",
        "spd_turbo": "أقصى سرعة آمنة",
        "th_std": "استخدام عادي",
        "th_fast": "استخدام سريع",
        "th_max": "أقصى قوة",
        "live_strip_lbl": "عرض مباشر للمربعات التي يتم حفظها:",
        "witness_strip_lbl": "سجل عينات هذه الجلسة:",
        "step4_title": "الخطوة 4 — صهر (دمج) أو نقل خرائطك إلى الذاكرة",
        "step4_sub": "اختر بطاقة الذاكرة أو القرص الذي تريد وضع الخرائط فيه:",
        "dd_sd_drive": "بطاقة الذاكرة أو القرص الوجهة",
        "step4_ready_msg": "اختر بالأسفل ما إذا كنت تريد صهر (دمج) خرائطك أو نقلها إلى الذاكرة المختارة.",
        "mass_ops_title": "إجراءات لجميع خرائطك المحفوظة:",
        "btn_all_merge_keep": "1. صهر (دمج) الكل في الذاكرة (الاحتفاظ بنسخة في الكمبيوتر)",
        "btn_all_merge_move": "2. صهر (دمج) الكل ونقلها (توفير مساحة في الكمبيوتر)",
        "btn_all_direct_move": "3. نقل الكل فقط إلى الذاكرة",
        "single_ops_title": "خرائطك المحفوظة (يمكنك أيضاً التحكم بكل خريطة على حدة):",
        "no_maps_yet": "لا توجد خرائط محفوظة على هذا القرص حالياً.",
        "btn_item_resume": "▶ متابعة التحميل",
        "btn_item_add_routes": "+ تحميل مسارات (.HWY)",
        "btn_item_merge_keep": "صهر (الاحتفاظ بنسخة)",
        "btn_item_merge_move": "صهر ونقل",
        "btn_item_direct_move": "نقل فقط",
        "btn_item_slim": "تقليل الحجم",
        "btn_item_del": "حذف",
        "transferring_msg": "جارٍ صهر ونقل الخرائط إلى الذاكرة ({pct:.0f}%)... يرجى الانتظار.",
        "transfer_done_msg": "تم بنجاح! خرائطك جاهزة الآن في بطاقة الذاكرة. يمكنك إزالتها بأمان.",
        "nav_s0": ("الخطوة 0", "اللغة"),
        "nav_s1": ("الخطوة 1", "توصيل الهاتف"),
        "nav_s2": ("الخطوة 2", "اختيار القرص"),
        "nav_s3": ("الخطوة 3", "تحميل الخريطة"),
        "nav_s4": ("الخطوة 4", "صهر / نقل"),
        "st_current": "[ الخطوة الحالية ]",
        "st_avail": "[ متاح ]",
        "st_locked": "[ مشغول ]",
        "st_pending": "[ قيد الانتظار ]",
        "lock_toast_busy": "يرجى الإيقاف مؤقتاً أو انتظار انتهاء العملية الحالية أولاً.",
        "lock_toast_no_order": "أرسل خريطة من هاتفك في الخطوة 1 أولاً.",
        "tag_removable": "[بطاقة ذاكرة خارجية]",
        "tag_local": "[قرص الكمبيوتر]",
        "free_lbl": "متاح",
    },
    "ru": {
        "step0_title": "ШАГ 0 — ВЫБЕРИТЕ ВАШ ЯЗЫК",
        "step0_sub": "Выберите язык для начала работы. Помощник проведёт вас шаг за шагом.",
        "step1_title": "ШАГ 1 — ПОДКЛЮЧЕНИЕ К ТЕЛЕФОНУ",
        "step1_sub": "Как только вы отправите выбранную зону с телефона, окно автоматически перейдёт к Шагу 2.",
        "cred_box_title": "ДАННЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ ТЕЛЕФОНА",
        "ip_wifi_lbl": "IP-АДРЕС (WI-FI / ЛОКАЛЬНАЯ СЕТЬ):",
        "pin_lbl": "PIN-КОД:",
        "ip_usb_lbl": "ПОДКЛЮЧЕНИЕ ЧЕРЕЗ USB-КАБЕЛЬ:",
        "usb_wait": "Активируется при включении «USB-модем» в настройках телефона",
        "opt_a_title": "ВАРИАНТ А: ЧЕРЕЗ WI-FI ИЛИ ТОЧКУ ДОСТУПА",
        "opt_a_body": "1. Подключите телефон и ПК к одному Wi-Fi (или точке доступа телефона).\n2. Нажмите «Отправить на ПК» в приложении.\n3. Программа сама перейдёт к Шагу 2.",
        "opt_b_title": "ВАРИАНТ Б: ЧЕРЕЗ USB-КАБЕЛЬ",
        "opt_b_body": "1. Подключите телефон к ПК кабелем USB.\n2. Включите «USB-модем» в настройках телефона.\n3. Нажмите «Отправить на ПК» в приложении.",
        "opt_c_title": "ВАРИАНТ В: ОТКРЫТЬ СОХРАНЁННЫЙ ФАЙЛ (.JSON)",
        "opt_c_body": "Если вы сохранили заказ в виде файла на компьютере:",
        "btn_pick_file": "ВЫБРАТЬ ФАЙЛ НА ПК",
        "waiting_order": "Ожидание отправки карты с вашего телефона...",
        "order_ready": "Заказ получен: {name}  |  Режим: {mode_str}  |  Примерный размер: {mb:.1f} MB",
        "btn_to_step2": "ПЕРЕЙТИ К ШАГУ 2: ВЫБОР ДИСКА >>",
        "btn_to_step4_direct": "К МОИМ СОХРАНЁННЫМ КАРТАМ (ШАГ 4)",
        "step2_title": "ШАГ 2 — ВЫБОР ДИСКА ДЛЯ ВРЕМЕННОГО ХРАНЕНИЯ",
        "dd_pc_drive": "Диск компьютера, где будет подготавливаться карта",
        "btn_refresh_drives": "ОБНОВИТЬ ДИСКИ",
        "space_ok": "Свободно на ПК: {pc_gb:.1f} GB  |  Требуется: {req_mb:.1f} MB  [МЕСТА ДОСТАТОЧНО]",
        "space_low": "Свободно на ПК: {pc_gb:.1f} GB  |  Требуется: {req_mb:.1f} MB  [НЕДОСТАТОЧНО МЕСТА]",
        "space_idle": "Свободно на ПК: {pc_gb:.1f} GB  |  Свободно на карте памяти: {sd_gb:.1f} GB",
        "step2_1_title": "ШАГ 2.1 — БЫСТРЫЙ ПРЕДПРОСМОТР (НЕОБЯЗАТЕЛЬНО)",
        "step2_1_desc": "Вы можете скачать 4 пробных квадрата, чтобы проверить внешний вид карты перед стартом.",
        "btn_fire_test": "ПОКАЗАТЬ 4 ПРОБНЫХ ОБРАЗЦА",
        "fire_testing": "Загрузка 4 пробных образцов...",
        "fire_ok": "Предпросмотр готов. Всё работает отлично.",
        "btn_back_step1": "< НАЗАД К ШАГУ 1",
        "btn_to_step3": "ПОДТВЕРДИТЬ И ПЕРЕЙТИ К ШАГУ 3 (ЗАГРУЗКА) >>",
        "step3_title": "ШАГ 3 — ЗАГРУЗКА КАРТЫ",
        "btn_go_step4": "ПЕРЕЙТИ К ШАГУ 4: СЛИЯНИЕ ИЛИ ПЕРЕНОС >>",
        "banner_ready_title": "ГОТОВО К ЗАПУСКУ",
        "banner_ready_sub": "Нажмите зелёную кнопку «СТАРТ / ПРОДОЛЖИТЬ» ниже для начала загрузки.",
        "banner_paused_title": "⏸  ПАУЗА",
        "banner_paused_sub": "Прогресс надёжно сохранён. Нажмите «СТАРТ / ПРОДОЛЖИТЬ», когда будете готовы.",
        "banner_net_title": "⚠  НЕТ ИНТЕРНЕТА — АВТОПАУЗА",
        "banner_net_sub": "Загрузка продолжится автоматически, как только появится соединение.",
        "banner_prep_title": "⏳  ПОДГОТОВКА — СТАРТ ЧЕРЕЗ ~{cd}",
        "banner_prep_sub": "Организация маршрутов и сетки карты перед загрузкой...",
        "banner_run_title": "⚡  ЗАГРУЗКА: {name} ({pct:.1f}%)",
        "banner_run_sub": "Осталось примерно: {eta}  |  Не отключайте диск.",
        "banner_done_title": "✔  ЗАГРУЗКА ЗАВЕРШЕНА НА 100%!",
        "banner_done_sub": "Нажмите синюю кнопку «ПЕРЕЙТИ К ШАГУ 4», чтобы слить или перенести карту на карту памяти.",
        "clock_active": "ПРОШЛО ВРЕМЕНИ",
        "clock_eta": "ОСТАЛОСЬ ВРЕМЕНИ",
        "clock_speed": "ТЕКУЩАЯ СКОРОСТЬ",
        "btn_start": "▶ СТАРТ / ПРОДОЛЖИТЬ",
        "btn_pause": "⏸ ПАУЗА",
        "btn_stop": "⏹ СОХРАНИТЬ И ВЫЙТИ",
        "dd_threads": "Мощность процессора",
        "dd_speed": "Скорость загрузки",
        "spd_slow": "Спокойная и безопасная",
        "spd_norm": "Нормальная (рекомендуется)",
        "spd_fast": "Быстрая",
        "spd_turbo": "Максимальная безопасная",
        "th_std": "Стандартный режим",
        "th_fast": "Быстрый режим",
        "th_max": "Максимальная мощность",
        "live_strip_lbl": "ЖИВОЙ ПРОСМОТР СОХРАНЯЕМЫХ УЧАСТКОВ:",
        "witness_strip_lbl": "ИСТОРИЯ ОБРАЗЦОВ ЭТОЙ СЕССИИ:",
        "step4_title": "ШАГ 4 — СЛИЯНИЕ ИЛИ ПЕРЕНОС КАРТ НА КАРТУ ПАМЯТИ",
        "step4_sub": "Выберите карту памяти или диск, куда нужно записать готовые карты:",
        "dd_sd_drive": "Целевая карта памяти или диск",
        "step4_ready_msg": "Выберите ниже: слить (объединить) карты с уже имеющимися на флешке или просто перенести их.",
        "mass_ops_title": "ДЕЙСТВИЯ ДЛЯ ВСЕХ СОХРАНЁННЫХ КАРТ:",
        "btn_all_merge_keep": "1. СЛИТЬ ВСЕ НА КАРТУ ПАМЯТИ (ОСТАВИТЬ КОПИЮ НА ПК)",
        "btn_all_merge_move": "2. СЛИТЬ ВСЕ И ПЕРЕМЕСТИТЬ (ОСВОБОДИТЬ МЕСТО НА ПК)",
        "btn_all_direct_move": "3. ПРОСТО ПЕРЕМЕСТИТЬ ВСЕ НА КАРТУ ПАМЯТИ",
        "single_ops_title": "ВАШИ СОХРАНЁННЫЕ КАРТЫ (УПРАВЛЕНИЕ ПО ОДНОЙ):",
        "no_maps_yet": "На этом диске пока нет сохранённых карт.",
        "btn_item_resume": "▶ ДОКАЧАТЬ",
        "btn_item_add_routes": "+ СКАЧАТЬ МАРШРУТЫ (.HWY)",
        "btn_item_merge_keep": "СЛИТЬ (ОСТАВИТЬ КОПИЮ)",
        "btn_item_merge_move": "СЛИТЬ И ПЕРЕМЕСТИТЬ",
        "btn_item_direct_move": "ТОЛЬКО ПЕРЕМЕСТИТЬ",
        "btn_item_slim": "УМЕНЬШИТЬ ВЕС",
        "btn_item_del": "УДАЛИТЬ",
        "transferring_msg": "Слияние и перенос карт на память ({pct:.0f}%)... Пожалуйста, подождите.",
        "transfer_done_msg": "Готово! Ваши карты слиты и записаны на выбранный накопитель. Можно извлекать.",
        "nav_s0": ("ШАГ 0", "Язык"),
        "nav_s1": ("ШАГ 1", "Телефон"),
        "nav_s2": ("ШАГ 2 и 2.1", "Выбор диска"),
        "nav_s3": ("ШАГ 3", "Загрузка"),
        "nav_s4": ("ШАГ 4", "Слияние / Перенос"),
        "st_current": "[ ТЕКУЩИЙ ШАГ ]",
        "st_avail": "[ ДОСТУПНО ]",
        "st_locked": "[ ЗАНЯТО ]",
        "st_pending": "[ ОЖИДАНИЕ ]",
        "lock_toast_busy": "Сначала поставьте на паузу или дождитесь завершения текущего процесса.",
        "lock_toast_no_order": "Сначала отправьте карту с телефона на Шаге 1.",
        "tag_removable": "[КАРТА ПАМЯТИ / USB]",
        "tag_local": "[ДИСК ПК]",
        "free_lbl": "Свободно",
    }
}
# Copiar fallback EN para los demás idiomas si falta alguna llave nueva, sin borrar las existentes
for _l in ("zh", "ja", "hi", "fr", "ar", "ru"):
    if _l not in I18N:
        I18N[_l] = {}
    for k, v in I18N["en"].items():
        if k not in I18N[_l]:
            I18N[_l][k] = v


# =============================================================================
# 1. DETECTOR INTELIGENTE DE IP Y UNIDADES
# =============================================================================
class NetworkUtils:

    @staticmethod
    def is_virtual_or_bogus_ip(ip: str) -> bool:
        if ip.startswith("127.") or ip.startswith("169.254.") or ip.startswith("192.168.56."):
            return True
        return False

    @classmethod
    def get_classified_ips(cls) -> dict:
        primary_ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.6)
            s.connect(("8.8.8.8", 80))
            cand = s.getsockname()[0]
            s.close()
            if not cls.is_virtual_or_bogus_ip(cand):
                primary_ip = cand
        except Exception:
            pass

        usb_ips = []
        other_lan_ips = []
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = info[4][0]
                if cls.is_virtual_or_bogus_ip(ip):
                    continue
                if ip.startswith("192.168.42.") or ip.startswith("192.168.225.") or ip.startswith("172.20.10."):
                    if ip not in usb_ips:
                        usb_ips.append(ip)
                elif ip != primary_ip and ip not in other_lan_ips:
                    other_lan_ips.append(ip)
        except Exception:
            pass

        if not primary_ip:
            primary_ip = other_lan_ips[0] if other_lan_ips else (usb_ips[0] if usb_ips else "127.0.0.1")

        return {
            "primary": primary_ip,
            "usb": usb_ips,
            "extra": [x for x in other_lan_ips if x != primary_ip]
        }

    @staticmethod
    def get_hardware_thread_counts():
        logical_cpus = os.cpu_count() or 4
        safe_t = max(8, min(12, logical_cpus))
        fast_t = max(16, min(28, int(logical_cpus * 2)))
        turbo_t = max(24, min(40, int(logical_cpus * 3)))
        return safe_t, fast_t, turbo_t

    @staticmethod
    def check_internet_ping_ms():
        try:
            t0 = time.time()
            r = requests.head("https://cp.cloudflare.com/generate_204", timeout=2.5)
            if 200 <= r.status_code < 400:
                return int((time.time() - t0) * 1000)
            return -1
        except Exception:
            return -1

    @staticmethod
    def list_available_drives(lang_code: str = "es"):
        tr = I18N.get(lang_code, I18N["es"])
        drives = []
        if os.name == "nt":
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter_idx in range(26):
                if bitmask & (1 << letter_idx):
                    drive_letter = f"{chr(65 + letter_idx)}:\\"
                    try:
                        usage = shutil.disk_usage(drive_letter)
                        free_gb = usage.free / (1024 ** 3)
                        total_gb = usage.total / (1024 ** 3)
                        drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_letter)
                        tag = tr["tag_removable"] if drive_type == 2 else tr["tag_local"]
                        drives.append({
                            "root": drive_letter,
                            "label": f"{drive_letter} {tag} — {tr['free_lbl']}: {free_gb:,.1f} GB / {total_gb:,.1f} GB",
                            "free_mb": usage.free / (1024 ** 2),
                            "is_removable": (drive_type == 2)
                        })
                    except Exception:
                        pass
        else:
            home = str(Path.home())
            usage = shutil.disk_usage(home)
            drives.append({
                "root": home,
                "label": f"{home} — {tr['free_lbl']}: {usage.free / (1024 ** 3):,.1f} GB",
                "free_mb": usage.free / (1024 ** 2),
                "is_removable": False
            })
        return drives


# =============================================================================
# 2. MOTOR DE SHADERS CYBERPUNK + PIP-BOY COMPILADO EN NUMBA C (NOGIL)
# =============================================================================
if HAS_NUMBA:
    @njit(nogil=True, fastmath=True, cache=True)
    def _numba_cyberpunk_shader_565(rgb_in: np.ndarray, style_idx: int) -> np.ndarray:
        h_in, w_in, _ = rgb_in.shape
        r_f = np.empty((256, 256), dtype=np.float32)
        g_f = np.empty((256, 256), dtype=np.float32)
        b_f = np.empty((256, 256), dtype=np.float32)

        if h_in == 512 and w_in == 512:
            inv_1020 = np.float32(1.0 / 1020.0)
            for y in range(256):
                y2 = y << 1
                for x in range(256):
                    x2 = x << 1
                    r_sum = int(rgb_in[y2, x2, 0]) + int(rgb_in[y2, x2 + 1, 0]) + int(rgb_in[y2 + 1, x2, 0]) + int(rgb_in[y2 + 1, x2 + 1, 0])
                    g_sum = int(rgb_in[y2, x2, 1]) + int(rgb_in[y2, x2 + 1, 1]) + int(rgb_in[y2 + 1, x2, 1]) + int(rgb_in[y2 + 1, x2 + 1, 1])
                    b_sum = int(rgb_in[y2, x2, 2]) + int(rgb_in[y2, x2 + 1, 2]) + int(rgb_in[y2 + 1, x2, 2]) + int(rgb_in[y2 + 1, x2 + 1, 2])
                    r_f[y, x] = r_sum * inv_1020
                    g_f[y, x] = g_sum * inv_1020
                    b_f[y, x] = b_sum * inv_1020
        else:
            inv_255 = np.float32(1.0 / 255.0)
            for y in range(256):
                for x in range(256):
                    r_f[y, x] = rgb_in[y, x, 0] * inv_255
                    g_f[y, x] = rgb_in[y, x, 1] * inv_255
                    b_f[y, x] = rgb_in[y, x, 2] * inv_255

        out = np.empty((256, 256, 3), dtype=np.uint8)

        if style_idx == 0:
            for y in range(256):
                for x in range(256):
                    ir = 1.0 - b_f[y, x]
                    ig = 1.0 - g_f[y, x]
                    ib = 1.0 - r_f[y, x]
                    ir = (ir if ir > 0.0 else 0.0) ** 1.45
                    ig = (ig if ig > 0.0 else 0.0) ** 1.42
                    ib = (ib if ib > 0.0 else 0.0) ** 1.35
                    cr = int(min(255.0, max(0.0, ir * 255.0 + 0.5)))
                    cg = int(min(255.0, max(0.0, ig * 255.0 + 0.5)))
                    cb = int(min(255.0, max(0.0, ib * 255.0 + 0.5)))
                    out[y, x, 0] = (cr >> 3) << 3
                    out[y, x, 1] = (cg >> 2) << 2
                    out[y, x, 2] = (cb >> 3) << 3
            return out

        is_kiroshi = (style_idx == 2)
        is_pipboy = (style_idx == 5)
        hwy_core = np.empty((256, 256), dtype=np.float32)
        blue_ramp_arr = np.empty((256, 256), dtype=np.float32)

        for y in range(256):
            for x in range(256):
                rv = r_f[y, x]
                gv = g_f[y, x]
                bv = b_f[y, x]
                lum = 0.299 * rv + 0.587 * gv + 0.114 * bv

                max_rb = rv if rv > bv else bv
                t_veg = (gv - max_rb - 0.012) / (0.063 + 1e-6)
                t_veg = min(1.0, max(0.0, t_veg))
                veg = t_veg * t_veg * (3.0 - 2.0 * t_veg)

                min_rg_bg = (rv - gv) if (rv - gv) < (bv - gv) else (bv - gv)
                t_poi = (min_rg_bg - 0.055) / (0.145 + 1e-6)
                t_poi = min(1.0, max(0.0, t_poi))
                poi = t_poi * t_poi * (3.0 - 2.0 * t_poi)

                t_w1 = min(1.0, max(0.0, (bv - rv - 0.045) / (0.095 + 1e-6)))
                t_w2 = min(1.0, max(0.0, (lum - 0.77) / (0.10 + 1e-6)))
                water = (t_w1 * t_w1 * (3.0 - 2.0 * t_w1)) * (t_w2 * t_w2 * (3.0 - 2.0 * t_w2)) * (1.0 - veg)

                road_gate = (1.0 - veg) * (1.0 - poi) * (1.0 - water * 0.92)
                br = (bv - rv if (bv - rv) > 0.0 else 0.0) * road_gate
                blue_ramp_arr[y, x] = br

                t_hc = min(1.0, max(0.0, (br - 0.075) / (0.10 + 1e-6)))
                hwy_core[y, x] = t_hc * t_hc * (3.0 - 2.0 * t_hc)

        for y in range(256):
            y0 = y - 1 if y > 0 else 0
            y1 = y + 1 if y < 255 else 255

            for x in range(256):
                x0 = x - 1 if x > 0 else 0
                x1 = x + 1 if x < 255 else 255

                max_d = np.float32(0.0)
                for dy in range(y0, y1 + 1):
                    for dx in range(x0, x1 + 1):
                        v_hc = hwy_core[dy, dx]
                        if v_hc > max_d:
                            max_d = v_hc

                rv = r_f[y, x]
                gv = g_f[y, x]
                bv = b_f[y, x]
                lum = 0.299 * rv + 0.587 * gv + 0.114 * bv
                dark = 1.0 - lum

                max_rb = rv if rv > bv else bv
                t_veg = min(1.0, max(0.0, (gv - max_rb - 0.012) / (0.063 + 1e-6)))
                veg = t_veg * t_veg * (3.0 - 2.0 * t_veg)

                min_rg_bg = (rv - gv) if (rv - gv) < (bv - gv) else (bv - gv)
                t_poi = min(1.0, max(0.0, (min_rg_bg - 0.055) / (0.145 + 1e-6)))
                poi = t_poi * t_poi * (3.0 - 2.0 * t_poi)

                t_w1 = min(1.0, max(0.0, (bv - rv - 0.045) / (0.095 + 1e-6)))
                t_w2 = min(1.0, max(0.0, (lum - 0.77) / (0.10 + 1e-6)))
                water = (t_w1 * t_w1 * (3.0 - 2.0 * t_w1)) * (t_w2 * t_w2 * (3.0 - 2.0 * t_w2)) * (1.0 - veg)

                hc = hwy_core[y, x]
                highway = min(1.0, max(0.0, hc * 0.65 + max_d * 0.35))

                br = blue_ramp_arr[y, x]
                t_st = min(1.0, max(0.0, (br - 0.018) / (0.057 + 1e-6)))
                street = (t_st * t_st * (3.0 - 2.0 * t_st)) * (1.0 - highway)

                t_ter = min(1.0, max(0.0, (lum - 0.68) / (0.27 + 1e-6)))
                terrain_tone = (0.38 + 0.62 * (t_ter * t_ter * (3.0 - 2.0 * t_ter))) * (1.0 - veg * 0.45)

                t_tm = min(1.0, max(0.0, (dark - 0.18) / (0.50 + 1e-6)))
                text_mask = (t_tm * t_tm * (3.0 - 2.0 * t_tm)) * (1.0 - highway * 0.85) * (1.0 - poi * 0.75)

                if is_pipboy:
                    or_v = (0.01 * terrain_tone) + water * 0.01
                    og_v = (0.18 * terrain_tone) + water * 0.30
                    ob_v = (0.03 * terrain_tone) + water * 0.10

                    or_v = or_v * (1.0 - street) + street * 0.05
                    og_v = og_v * (1.0 - street) + street * 0.48
                    ob_v = ob_v * (1.0 - street) + street * 0.12

                    or_v = or_v * (1.0 - highway) + highway * 0.14
                    og_v = og_v * (1.0 - highway) + highway * 0.92
                    ob_v = ob_v * (1.0 - highway) + highway * 0.22

                    or_v = or_v * (1.0 - poi) + poi * 0.28
                    og_v = og_v * (1.0 - poi) + poi * 0.85
                    ob_v = ob_v * (1.0 - poi) + poi * 0.20

                    or_v = or_v * (1.0 - text_mask) + text_mask * 0.86
                    og_v = og_v * (1.0 - text_mask) + text_mask * 1.00
                    ob_v = ob_v * (1.0 - text_mask) + text_mask * 0.88
                else:
                    if is_kiroshi:
                        or_v = (0.24 * terrain_tone) + water * 0.05
                        og_v = (0.04 * terrain_tone) + water * 0.18
                        ob_v = (0.20 * terrain_tone) + water * 0.35
                        or_v = or_v * (1.0 - street) + street * 0.58
                        og_v = og_v * (1.0 - street) + street * 0.10
                        ob_v = ob_v * (1.0 - street) + street * 0.44
                        or_v = or_v * (1.0 - highway) + highway * 1.00
                        og_v = og_v * (1.0 - highway) + highway * 0.12
                        ob_v = ob_v * (1.0 - highway) + highway * 0.22
                    else:
                        or_v = (0.02 * terrain_tone) + water * 0.02
                        og_v = (0.20 * terrain_tone) + water * 0.30
                        ob_v = (0.34 * terrain_tone) + water * 0.48
                        or_v = or_v * (1.0 - street) + street * 0.08
                        og_v = og_v * (1.0 - street) + street * 0.46
                        ob_v = ob_v * (1.0 - street) + street * 0.64
                        or_v = or_v * (1.0 - highway) + highway * 1.00
                        og_v = og_v * (1.0 - highway) + highway * 0.08
                        ob_v = ob_v * (1.0 - highway) + highway * 0.20

                    or_v = or_v * (1.0 - poi) + poi * 0.10
                    og_v = og_v * (1.0 - poi) + poi * 0.95
                    ob_v = ob_v * (1.0 - poi) + poi * 0.48
                    or_v = or_v * (1.0 - text_mask) + text_mask * 0.95
                    og_v = og_v * (1.0 - text_mask) + text_mask * 0.98
                    ob_v = ob_v * (1.0 - text_mask) + text_mask * 1.00

                cr = int(min(255.0, max(0.0, or_v * 255.0 + 0.5)))
                cg = int(min(255.0, max(0.0, og_v * 255.0 + 0.5)))
                cb = int(min(255.0, max(0.0, ob_v * 255.0 + 0.5)))

                out[y, x, 0] = (cr >> 3) << 3
                out[y, x, 1] = (cg >> 2) << 2
                out[y, x, 2] = (cb >> 3) << 3

        return out

class CyberpunkShaderEnginePy:
    @staticmethod
    def _smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
        t = np.clip((x - edge0) / ((edge1 - edge0) + 1e-6), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    @staticmethod
    def _dilate_3x3(mask: np.ndarray) -> np.ndarray:
        p = np.pad(mask, 1, mode="edge")
        return np.maximum.reduce([
            p[0:-2, 0:-2], p[0:-2, 1:-1], p[0:-2, 2:],
            p[1:-1, 0:-2], p[1:-1, 1:-1], p[1:-1, 2:],
            p[2:,   0:-2], p[2:,   1:-1], p[2:,   2:]
        ])

    @staticmethod
    def _quantize_565(arr_float: np.ndarray, bits: int) -> np.ndarray:
        c = np.clip(arr_float * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
        shift = 8 - bits
        return (c >> shift) << shift

    @classmethod
    def apply_shader_to_rgb_array(cls, rgb_uint8: np.ndarray, style_idx: int) -> np.ndarray:
        if HAS_NUMBA and rgb_uint8.shape[0] in (256, 512) and rgb_uint8.shape[1] in (256, 512):
            return _numba_cyberpunk_shader_565(np.ascontiguousarray(rgb_uint8, dtype=np.uint8), int(style_idx))

        if rgb_uint8.shape[0] == 512 and rgb_uint8.shape[1] == 512:
            rgb_uint8 = rgb_uint8.reshape(256, 2, 256, 2, 3).mean(axis=(1, 3)).astype(np.uint8)
        rgb = rgb_uint8.astype(np.float32) * (1.0 / 255.0)
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

        if style_idx == 0:
            inv_r = np.power(np.clip(1.0 - b, 0.0, 1.0), 1.45)
            inv_g = np.power(np.clip(1.0 - g, 0.0, 1.0), 1.42)
            inv_b = np.power(np.clip(1.0 - r, 0.0, 1.0), 1.35)
            return np.dstack((cls._quantize_565(inv_r, 5), cls._quantize_565(inv_g, 6), cls._quantize_565(inv_b, 5)))

        is_kiroshi = (style_idx == 2)
        is_pipboy = (style_idx == 5)
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        dark = 1.0 - lum
        veg = cls._smoothstep(0.012, 0.075, g - np.maximum(r, b))
        poi = cls._smoothstep(0.055, 0.20, np.minimum(r - g, b - g))
        water = cls._smoothstep(0.045, 0.14, b - r) * cls._smoothstep(0.77, 0.87, lum) * (1.0 - veg)
        road_gate = (1.0 - veg) * (1.0 - poi) * (1.0 - water * 0.92)
        blue_ramp = np.maximum(0.0, b - r) * road_gate
        hwy_core = cls._smoothstep(0.075, 0.175, blue_ramp)
        highway = np.clip(hwy_core * 0.65 + cls._dilate_3x3(hwy_core) * 0.35, 0.0, 1.0)
        street = cls._smoothstep(0.018, 0.075, blue_ramp) * (1.0 - highway)
        terrain_tone = (0.38 + 0.62 * cls._smoothstep(0.68, 0.95, lum)) * (1.0 - veg * 0.45)
        text_mask = cls._smoothstep(0.18, 0.68, dark) * (1.0 - highway * 0.85) * (1.0 - poi * 0.75)

        if is_pipboy:
            out_r = ((0.01 * terrain_tone) + water * 0.01) * (1.0 - street) + street * 0.05
            out_g = ((0.18 * terrain_tone) + water * 0.30) * (1.0 - street) + street * 0.48
            out_b = ((0.03 * terrain_tone) + water * 0.10) * (1.0 - street) + street * 0.12
            out_r = out_r * (1.0 - highway) + highway * 0.14
            out_g = out_g * (1.0 - highway) + highway * 0.92
            out_b = out_b * (1.0 - highway) + highway * 0.22
            out_r = out_r * (1.0 - poi) + poi * 0.28
            out_g = out_g * (1.0 - poi) + poi * 0.85
            out_b = out_b * (1.0 - poi) + poi * 0.20
            out_r = np.clip(out_r * (1.0 - text_mask) + text_mask * 0.86, 0.0, 1.0)
            out_g = np.clip(out_g * (1.0 - text_mask) + text_mask * 1.00, 0.0, 1.0)
            out_b = np.clip(out_b * (1.0 - text_mask) + text_mask * 0.88, 0.0, 1.0)
            return np.dstack((cls._quantize_565(out_r, 5), cls._quantize_565(out_g, 6), cls._quantize_565(out_b, 5)))

        if is_kiroshi:
            out_r = ((0.24 * terrain_tone) + water * 0.05) * (1.0 - street) + street * 0.58
            out_g = ((0.04 * terrain_tone) + water * 0.18) * (1.0 - street) + street * 0.10
            out_b = ((0.20 * terrain_tone) + water * 0.35) * (1.0 - street) + street * 0.44
            out_r = out_r * (1.0 - highway) + highway * 1.00
            out_g = out_g * (1.0 - highway) + highway * 0.12
            out_b = out_b * (1.0 - highway) + highway * 0.22
        else:
            out_r = ((0.02 * terrain_tone) + water * 0.02) * (1.0 - street) + street * 0.08
            out_g = ((0.20 * terrain_tone) + water * 0.30) * (1.0 - street) + street * 0.46
            out_b = ((0.34 * terrain_tone) + water * 0.48) * (1.0 - street) + street * 0.64
            out_r = out_r * (1.0 - highway) + highway * 1.00
            out_g = out_g * (1.0 - highway) + highway * 0.08
            out_b = out_b * (1.0 - highway) + highway * 0.20

        out_r = out_r * (1.0 - poi) + poi * 0.10
        out_g = out_g * (1.0 - poi) + poi * 0.95
        out_b = out_b * (1.0 - poi) + poi * 0.48
        out_r = np.clip(out_r * (1.0 - text_mask) + text_mask * 0.95, 0.0, 1.0)
        out_g = np.clip(out_g * (1.0 - text_mask) + text_mask * 0.98, 0.0, 1.0)
        out_b = np.clip(out_b * (1.0 - text_mask) + text_mask * 1.00, 0.0, 1.0)

        return np.dstack((cls._quantize_565(out_r, 5), cls._quantize_565(out_g, 6), cls._quantize_565(out_b, 5)))


# =============================================================================
# 3. CODEC BINARIO CUSTOM QOI-565 (NUMBA NOGIL - IDÉNTICO AL C++ DEL RELOJ)
# =============================================================================
if HAS_NUMBA:
    @njit(nogil=True, cache=True)
    def _numba_encode_custom_qoi565(raw: np.ndarray, w: int, h: int) -> np.ndarray:
        total_px = w * h
        out = np.empty(total_px * 3 + 8, dtype=np.uint8)
        p = 0
        cache = np.zeros(64, dtype=np.uint16)
        prev_px = np.uint16(0)
        run = 0

        for i in range(total_px):
            r = raw[i * 3]
            g = raw[i * 3 + 1]
            b = raw[i * 3 + 2]

            r5 = (r >> 3) & 0x1F
            g6 = (g >> 2) & 0x3F
            b5 = (b >> 3) & 0x1F
            px = np.uint16((r5 << 11) | (g6 << 5) | b5)

            if px == prev_px:
                run += 1
                if run == 64:
                    out[p] = 0x3F
                    p += 1
                    run = 0
            else:
                if run > 0:
                    out[p] = run - 1
                    p += 1
                    run = 0

                idx = (px ^ (px >> 3)) & 63
                if cache[idx] == px:
                    out[p] = 0x40 | idx
                    p += 1
                else:
                    out[p] = 0x80
                    out[p + 1] = px & 0xFF
                    out[p + 2] = (px >> 8) & 0xFF
                    p += 3
                    cache[idx] = px
                prev_px = px

        if run > 0:
            out[p] = run - 1
            p += 1

        return out[:p]


class QoiBinaryCodecPy:

    @staticmethod
    def encode_rgb_array_to_qoi565(rgb_arr: np.ndarray) -> bytes:
        h, w, _ = rgb_arr.shape
        flat = np.ascontiguousarray(rgb_arr, dtype=np.uint8).ravel()
        if HAS_NUMBA:
            return _numba_encode_custom_qoi565(flat, w, h).tobytes()

        raw = flat.tobytes()
        total_px = w * h
        out = bytearray()
        cache = [0] * 64
        prev_px = 0
        run = 0

        for off in range(0, total_px * 3, 3):
            r = raw[off]
            g = raw[off + 1]
            b = raw[off + 2]
            px = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

            if px == prev_px:
                run += 1
                if run == 64:
                    out.append(0x3F)
                    run = 0
            else:
                if run > 0:
                    out.append(run - 1)
                    run = 0
                idx = (px ^ (px >> 3)) & 63
                if cache[idx] == px:
                    out.append(0x40 | idx)
                else:
                    out.append(0x80)
                    out.append(px & 0xFF)
                    out.append((px >> 8) & 0xFF)
                    cache[idx] = px
                prev_px = px

        if run > 0:
            out.append(run - 1)

        return bytes(out)

    @staticmethod
    def decode_qoi_to_base64_png(qoi_data: bytes) -> str:
        w, h = 256, 256
        total_px = w * h
        rgb_out = bytearray(total_px * 3)
        cache = [0] * 64

        in_idx = 0
        out_idx = 0
        prev_px = 0
        comp_len = len(qoi_data)

        while in_idx < comp_len and out_idx < total_px:
            op = qoi_data[in_idx]
            in_idx += 1
            tag = op & 0xC0

            if tag == 0x00:
                run = (op & 0x3F) + 1
                for _ in range(run):
                    if out_idx < total_px:
                        rgb_out[out_idx * 3] = ((prev_px >> 11) & 0x1F) << 3
                        rgb_out[out_idx * 3 + 1] = ((prev_px >> 5) & 0x3F) << 2
                        rgb_out[out_idx * 3 + 2] = (prev_px & 0x1F) << 3
                        out_idx += 1
            elif tag == 0x40:
                idx = op & 0x3F
                px = cache[idx]
                prev_px = px
                if out_idx < total_px:
                    rgb_out[out_idx * 3] = ((px >> 11) & 0x1F) << 3
                    rgb_out[out_idx * 3 + 1] = ((px >> 5) & 0x3F) << 2
                    rgb_out[out_idx * 3 + 2] = (px & 0x1F) << 3
                    out_idx += 1
            elif op == 0x80:
                if in_idx + 1 >= comp_len:
                    break
                px = qoi_data[in_idx] | (qoi_data[in_idx + 1] << 8)
                in_idx += 2
                idx = (px ^ (px >> 3)) & 63
                cache[idx] = px
                prev_px = px
                if out_idx < total_px:
                    rgb_out[out_idx * 3] = ((px >> 11) & 0x1F) << 3
                    rgb_out[out_idx * 3 + 1] = ((px >> 5) & 0x3F) << 2
                    rgb_out[out_idx * 3 + 2] = (px & 0x1F) << 3
                    out_idx += 1

        pil_img = Image.frombytes("RGB", (w, h), bytes(rgb_out))
        pil_img.thumbnail((84, 84))
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")


class TileAuditorPy:

    @staticmethod
    def decode_and_audit(raw_bytes: bytes, allow_hi_res_512: bool = False):
        if not raw_bytes or len(raw_bytes) < 85:
            return None
        is_png = raw_bytes[:4] == b"\x89PNG"
        is_jpg = raw_bytes[:3] == b"\xff\xd8\xff"
        if not (is_png or is_jpg):
            return None
        try:
            img = Image.open(BytesIO(raw_bytes)).convert("RGB")
            if img.width < 128 or img.height < 128:
                return None
            if allow_hi_res_512 and img.size == (512, 512):
                return img
            if img.size != (256, 256):
                img = img.resize((256, 256), Image.Resampling.BILINEAR)
            return img
        except Exception:
            return None

    @staticmethod
    def is_carto_watermark(img: Image.Image) -> bool:
        w, h = img.size
        p1 = img.getpixel((4, 4))
        p2 = img.getpixel((w - 5, 4))
        p3 = img.getpixel((4, h - 5))
        p4 = img.getpixel((w - 5, h - 5))
        if p1 == p2 == p3 == p4 and p1[0] == p1[1] == p1[2] and (28 <= p1[0] <= 64):
            base_v = p1[0]
            bright_hits = 0
            for d in range(50, min(206, w - 10), 4):
                if img.getpixel((d, d))[2] > base_v + 35 or img.getpixel((w // 2, d))[2] > base_v + 35:
                    bright_hits += 1
            if bright_hits >= 3:
                return True
        return False

if HAS_NUMBA:
    _dummy_rgb = np.zeros((256, 256, 3), dtype=np.uint8)
    _numba_cyberpunk_shader_565(_dummy_rgb, 1)
    _numba_encode_custom_qoi565(_dummy_rgb.ravel(), 256, 256)


# =============================================================================
# 4. EMPACADOR Y FUSIONADOR DE CLÚSTERES 32x32 COLUMN-MAJOR
# =============================================================================
class ClusterStorageHelper:
    HEADER_SIZE = 8192

    @staticmethod
    def calc_local_idx(tx: int, ty: int) -> int:
        return (tx % 32) * 32 + (ty % 32)

    @classmethod
    def inspect_existing_cluster(cls, qoi_path: Path) -> set:
        if not qoi_path.exists():
            return set()
        try:
            file_len = qoi_path.stat().st_size
            if file_len <= cls.HEADER_SIZE:
                return set()
            with open(qoi_path, "rb") as f:
                hdr = f.read(cls.HEADER_SIZE)
            if len(hdr) < cls.HEADER_SIZE:
                return set()
            unpacked = struct.unpack("<2048I", hdr)
            valid = set()
            for idx in range(1024):
                off = unpacked[idx * 2]
                length = unpacked[idx * 2 + 1]
                if off >= cls.HEADER_SIZE and length > 20 and (off + length) <= file_len:
                    valid.add(idx)
            return valid
        except Exception:
            return set()

    @classmethod
    def load_existing_cluster_into_ram(cls, qoi_path: Path):
        if not qoi_path.exists():
            return bytearray(cls.HEADER_SIZE), bytearray()
        try:
            with open(qoi_path, "rb") as f:
                data = f.read()
            if len(data) >= cls.HEADER_SIZE:
                return bytearray(data[:cls.HEADER_SIZE]), bytearray(data[cls.HEADER_SIZE:])
        except Exception:
            pass
        return bytearray(cls.HEADER_SIZE), bytearray()

    @classmethod
    def atomic_save_cluster(cls, out_filepath: Path, header: bytearray, payload: bytearray):
        tmp_path = out_filepath.with_suffix(".QOI.TMP")
        with open(tmp_path, "wb") as f:
            f.write(header)
            f.write(payload)
        os.replace(tmp_path, out_filepath)

    @classmethod
    def merge_two_cluster_files(cls, src_qoi: Path, dst_qoi: Path) -> int:
        if not dst_qoi.exists() or dst_qoi.stat().st_size <= cls.HEADER_SIZE:
            shutil.copy2(src_qoi, dst_qoi)
            return 1

        with open(src_qoi, "rb") as fs:
            src_data = fs.read()
        if len(src_data) <= cls.HEADER_SIZE:
            return 0

        dst_hdr, dst_payload = cls.load_existing_cluster_into_ram(dst_qoi)
        fmt_hdr = "<2048I"
        src_unpacked = struct.unpack(fmt_hdr, src_data[:cls.HEADER_SIZE])
        dst_unpacked = struct.unpack(fmt_hdr, dst_hdr)

        current_offset = cls.HEADER_SIZE + len(dst_payload)
        added_tiles = 0
        fmt_pair = "<II"

        for idx in range(1024):
            s_off = src_unpacked[idx * 2]
            s_len = src_unpacked[idx * 2 + 1]
            d_off = dst_unpacked[idx * 2]
            d_len = dst_unpacked[idx * 2 + 1]

            if s_off >= cls.HEADER_SIZE and s_len > 20 and (s_off + s_len) <= len(src_data):
                if d_off < cls.HEADER_SIZE or d_len <= 20:
                    tile_bytes = src_data[s_off:s_off + s_len]
                    struct.pack_into(fmt_pair, dst_hdr, idx * 8, current_offset, s_len)
                    dst_payload.extend(tile_bytes)
                    current_offset += s_len
                    added_tiles += 1

        if added_tiles > 0:
            cls.atomic_save_cluster(dst_qoi, dst_hdr, dst_payload)
        return added_tiles


# =============================================================================
# 4B. COMPILADOR STREAMING CON AUTO-SUBDIVISIÓN Y FUSIONADOR DE RUTAS (.HWY)
# =============================================================================
class HwyGraphCompilerPy:
    MAX_VRAM_ARENA_BYTES = 1950000
    CELL_DEG = 0.02
    HALO_DEG = 0.015

    OVERPASS_MIRRORS = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
    ]

    @staticmethod
    def fast_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        x = (lon2 - lon1) * math.cos((lat1 + lat2) * 0.00872664626)
        y = (lat2 - lat1)
        return math.sqrt(x * x + y * y) * 111319.9

    @classmethod
    def _densify_way_points(cls, way_pts: list, max_seg_m: float) -> list:
        if len(way_pts) < 2 or max_seg_m <= 0.0:
            return way_pts
        out = [way_pts[0]]
        for i in range(1, len(way_pts)):
            lat1, lon1 = out[-1]
            lat2, lon2 = way_pts[i]
            d_m = cls.fast_distance_m(lat1, lon1, lat2, lon2)
            if d_m > max_seg_m:
                steps = min(16, int(d_m // max_seg_m) + 1)
                d_lat = (lat2 - lat1) / float(steps)
                d_lon = (lon2 - lon1) / float(steps)
                for s in range(1, steps):
                    out.append((lat1 + d_lat * s, lon1 + d_lon * s))
            out.append((lat2, lon2))
        return out

    @classmethod
    def write_hwy_binary(cls, filepath: Path, ways_subset: list, bounds=None, precision_digits: int = 5) -> tuple:
        fmt_hdr = "<II"
        fmt_node = "<ffI"
        fmt_edge = "<IIf"

        candidate_passes = [
            (precision_digits, 1),
            (max(4, precision_digits - 1), 2),
            (3, 4),
        ]

        for (prec, stride) in candidate_passes:
            coord_hits = {}
            if stride > 1:
                for (way_pts, _) in ways_subset:
                    for (pt_lat, pt_lon) in way_pts:
                        if bounds is not None:
                            b_s, b_n, b_w, b_e = bounds
                            if not (b_s <= pt_lat <= b_n and b_w <= pt_lon <= b_e):
                                continue
                        k = (round(pt_lat, prec), round(pt_lon, prec))
                        coord_hits[k] = coord_hits.get(k, 0) + 1

            node_map = {}
            nodes_list = []
            edges_dict = {}

            for (way_pts, oneway_mode) in ways_subset:
                prev_idx = None
                prev_lat, prev_lon = 0.0, 0.0
                accum_dist = 0.0
                last_pt_idx = len(way_pts) - 1

                for idx_pt, (pt_lat, pt_lon) in enumerate(way_pts):
                    if bounds is not None:
                        b_s, b_n, b_w, b_e = bounds
                        if not (b_s <= pt_lat <= b_n and b_w <= pt_lon <= b_e):
                            prev_idx = None
                            accum_dist = 0.0
                            continue

                    key = (round(pt_lat, prec), round(pt_lon, prec))
                    if prev_idx is not None:
                        accum_dist += cls.fast_distance_m(prev_lat, prev_lon, pt_lat, pt_lon)

                    if stride > 1 and prev_idx is not None and idx_pt != 0 and idx_pt != last_pt_idx:
                        if coord_hits.get(key, 0) < 2 and (idx_pt % stride != 0):
                            prev_lat, prev_lon = pt_lat, pt_lon
                            continue

                    u_idx = node_map.get(key)
                    if u_idx is None:
                        u_idx = len(nodes_list)
                        node_map[key] = u_idx
                        nodes_list.append((pt_lat, pt_lon))

                    if prev_idx is not None and prev_idx != u_idx:
                        d_m = max(1.0, accum_dist)
                        if oneway_mode == -1:
                            old_d = edges_dict.get((u_idx, prev_idx))
                            if old_d is None or d_m < old_d:
                                edges_dict[(u_idx, prev_idx)] = d_m
                        elif oneway_mode == 1:
                            old_d = edges_dict.get((prev_idx, u_idx))
                            if old_d is None or d_m < old_d:
                                edges_dict[(prev_idx, u_idx)] = d_m
                        else:
                            old_d1 = edges_dict.get((prev_idx, u_idx))
                            if old_d1 is None or d_m < old_d1:
                                edges_dict[(prev_idx, u_idx)] = d_m
                            old_d2 = edges_dict.get((u_idx, prev_idx))
                            if old_d2 is None or d_m < old_d2:
                                edges_dict[(u_idx, prev_idx)] = d_m
                        accum_dist = 0.0

                    prev_idx = u_idx
                    prev_lat, prev_lon = pt_lat, pt_lon

            num_n = len(nodes_list)
            num_e = len(edges_dict)
            if num_n == 0 or num_e == 0:
                return 0, 0

            vram_needed = (num_n * 20) + (num_e * 12) + 8192
            if vram_needed <= cls.MAX_VRAM_ARENA_BYTES or (prec == 3 and stride == 4):
                buf = bytearray()
                buf.extend(struct.pack(fmt_hdr, num_n, num_e))
                for (n_lat, n_lon) in nodes_list:
                    buf.extend(struct.pack(fmt_node, float(n_lat), float(n_lon), 0))
                for (u, v), dist_m in edges_dict.items():
                    buf.extend(struct.pack(fmt_edge, int(u), int(v), float(dist_m)))

                tmp_f = filepath.with_suffix(".HWY.TMP")
                with open(tmp_f, "wb") as fh:
                    fh.write(buf)
                os.replace(tmp_f, filepath)
                return num_n, num_e

        return 0, 0

    @classmethod
    def read_hwy_binary(cls, filepath: Path):
        if not filepath.exists() or filepath.stat().st_size < 20:
            return [], []
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            if raw[:8].startswith(b"EXOHWY"):
                return [], []
            fmt_hdr = "<II"
            fmt_node = "<ffI"
            fmt_edge = "<IIf"
            num_n, num_e = struct.unpack_from(fmt_hdr, raw, 0)
            expected_len = 8 + (num_n * 12) + (num_e * 12)
            if len(raw) < expected_len:
                return [], []

            nodes = []
            off = 8
            for _ in range(num_n):
                lat, lon, _ = struct.unpack_from(fmt_node, raw, off)
                nodes.append((lat, lon))
                off += 12

            edges = []
            for _ in range(num_e):
                u, v, w = struct.unpack_from(fmt_edge, raw, off)
                edges.append((u, v, w))
                off += 12
            return nodes, edges
        except Exception:
            return [], []

    @classmethod
    def merge_two_hwy_files(cls, src_hwy: Path, dst_hwy: Path) -> int:
        if not dst_hwy.exists() or dst_hwy.stat().st_size < 20:
            shutil.copy2(src_hwy, dst_hwy)
            return 1

        src_nodes, src_edges = cls.read_hwy_binary(src_hwy)
        if not src_nodes or not src_edges:
            return 0

        dst_nodes, dst_edges = cls.read_hwy_binary(dst_hwy)
        if not dst_nodes or not dst_edges:
            shutil.copy2(src_hwy, dst_hwy)
            return len(src_nodes)

        node_map = {}
        merged_nodes = []
        for idx, (lat, lon) in enumerate(dst_nodes):
            key = (round(lat, 5), round(lon, 5))
            node_map[key] = idx
            merged_nodes.append((lat, lon))

        src_to_merged = {}
        added_nodes = 0
        for s_idx, (lat, lon) in enumerate(src_nodes):
            key = (round(lat, 5), round(lon, 5))
            m_idx = node_map.get(key)
            if m_idx is None:
                m_idx = len(merged_nodes)
                node_map[key] = m_idx
                merged_nodes.append((lat, lon))
                added_nodes += 1
            src_to_merged[s_idx] = m_idx

        edge_set = set((u, v) for (u, v, _) in dst_edges)
        merged_edges = list(dst_edges)
        added_edges = 0

        for (su, sv, w) in src_edges:
            mu = src_to_merged.get(su)
            mv = src_to_merged.get(sv)
            if mu is not None and mv is not None and mu != mv:
                if (mu, mv) not in edge_set:
                    edge_set.add((mu, mv))
                    merged_edges.append((mu, mv, w))
                    added_edges += 1

        if added_nodes == 0 and added_edges == 0:
            return 0

        vram_needed = (len(merged_nodes) * 20) + (len(merged_edges) * 12) + 8192
        if vram_needed > cls.MAX_VRAM_ARENA_BYTES:
            if len(src_edges) > len(dst_edges):
                shutil.copy2(src_hwy, dst_hwy)
                return len(src_nodes)
            return 0

        buf = bytearray()
        buf.extend(struct.pack("<II", len(merged_nodes), len(merged_edges)))
        for (n_lat, n_lon) in merged_nodes:
            buf.extend(struct.pack("<ffI", float(n_lat), float(n_lon), 0))
        for (u, v, dist_m) in merged_edges:
            buf.extend(struct.pack("<IIf", int(u), int(v), float(dist_m)))

        tmp_f = dst_hwy.with_suffix(".HWY.TMP")
        with open(tmp_f, "wb") as fh:
            fh.write(buf)
        os.replace(tmp_f, dst_hwy)
        return added_nodes

    @staticmethod
    def _build_tight_subboxes(s_lim: float, n_lim: float, w_lim: float, e_lim: float, rings: list, has_poly: bool, max_step: float) -> list:
        boxes = []
        lat_span = max(0.001, n_lim - s_lim)
        num_bands = max(1, int(math.ceil(lat_span / max_step)))
        band_step = lat_span / float(num_bands)

        for b in range(num_bands):
            bs = s_lim + b * band_step
            bn = n_lim if (b == num_bands - 1) else (s_lim + (b + 1) * band_step)
            min_lon_b, max_lon_b = w_lim, e_lim

            if has_poly and rings:
                f_min, f_max = 1e9, -1e9
                for ring in rings:
                    if not ring:
                        continue
                    prev_lat, prev_lon = ring[-1][0], ring[-1][1]
                    for pt in ring:
                        clat, clon = pt[0], pt[1]
                        if bs <= clat <= bn:
                            if clon < f_min: f_min = clon
                            if clon > f_max: f_max = clon
                        seg_s, seg_n = min(prev_lat, clat), max(prev_lat, clat)
                        if seg_n >= bs and seg_s <= bn and abs(clat - prev_lat) > 1e-9:
                            for clip_lat in (bs, bn):
                                if seg_s <= clip_lat <= seg_n:
                                    t = (clip_lat - prev_lat) / (clat - prev_lat)
                                    clip_lon = prev_lon + t * (clon - prev_lon)
                                    if clip_lon < f_min: f_min = clip_lon
                                    if clip_lon > f_max: f_max = clip_lon
                        prev_lat, prev_lon = clat, clon
                if f_min <= f_max:
                    min_lon_b = max(w_lim, f_min - 0.02)
                    max_lon_b = min(e_lim, f_max + 0.02)
                else:
                    continue

            lon_span = max(0.001, max_lon_b - min_lon_b)
            num_cols = max(1, int(math.ceil(lon_span / max_step)))
            col_step = lon_span / float(num_cols)
            for c in range(num_cols):
                cw = min_lon_b + c * col_step
                ce = max_lon_b if (c == num_cols - 1) else (min_lon_b + (c + 1) * col_step)
                boxes.append((bs, cw, bn, ce))

        return boxes if boxes else [(s_lim, w_lim, n_lim, e_lim)]

    @staticmethod
    def _build_urban_cluster_boxes(raw_cells: list, s_lim: float, n_lim: float, w_lim: float, e_lim: float) -> list:
        if not raw_cells:
            return []
        cell_step = 0.38
        buckets = {}
        for c in raw_cells:
            tx, ty = c[0], c[1]
            lat = tile_y_to_lat(ty + 0.5, 16)
            lon = tile_x_to_lon(tx + 0.5, 16)
            if s_lim <= lat <= n_lim and w_lim <= lon <= e_lim:
                bx = int((lon + 180.0) / cell_step)
                by = int((lat + 90.0) / cell_step)
                key = (bx, by)
                if key not in buckets:
                    buckets[key] = [lat, lat, lon, lon]
                else:
                    b_bounds = buckets[key]
                    if lat < b_bounds[0]: b_bounds[0] = lat
                    if lat > b_bounds[1]: b_bounds[1] = lat
                    if lon < b_bounds[2]: b_bounds[2] = lon
                    if lon > b_bounds[3]: b_bounds[3] = lon

        pad = 0.018
        out_boxes = []
        for _, (min_lat, max_lat, min_lon, max_lon) in sorted(buckets.items()):
            bs = max(s_lim, min_lat - pad)
            bn = min(n_lim, max_lat + pad)
            bw = max(w_lim, min_lon - pad)
            be = min(e_lim, max_lon + pad)
            if bn > bs and be > bw:
                out_boxes.append((bs, bw, bn, be))
        return out_boxes

    @classmethod
    def compile_osm_hierarchy(cls, rec: dict, job_dir: Path, progress_cb=None, cancel_check=None, pause_check=None, kb_cb=None):
        sectors_dir = job_dir / "SECTORS"
        sectors_dir.mkdir(parents=True, exist_ok=True)
        arterial_path = job_dir / "ARTERIAL.HWY"

        prof = rec.get("route_profile_idx", 1)
        s, n = min(rec["south"], rec["north"]), max(rec["south"], rec["north"])
        w, e = min(rec["west"], rec["east"]), max(rec["west"], rec["east"])
        has_poly = rec.get("has_custom_polygon", False)
        rings = rec.get("selection_rings", [])
        area_deg2 = abs(n - s) * abs(e - w)

        backbone_rx = "^(motorway|trunk|primary|secondary|tertiary|unclassified|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"
        local_rx = (
            "^(residential|living_street|pedestrian|service|road)$" if prof == 1 else
            "^(residential|living_street|pedestrian|service|road|footway|steps|path|track)$"
        )
        full_rx = (
            backbone_rx if prof == 0 else
            "^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street|service|road|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$" if prof == 1 else
            "^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street|service|road|pedestrian|footway|steps|path|track|corridor|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"
        )

        # ESTRATEGIA ANTI-BLOQUEO:
        # 1) Si el área es grande (ej. Veracruz), separar Red Troncal (ligera) + Cajas Urbanas donde realmente hay pueblos.
        # 2) Concurrencia secuencial rotando espejos + streaming en tiempo real + auto-subdivisión si un bloque es muy denso.
        queries_to_run = []
        if area_deg2 > 1.8 and prof > 0:
            trunk_boxes = cls._build_tight_subboxes(s, n, w, e, rings, has_poly, max_step=1.35)
            for tb in trunk_boxes:
                queries_to_run.append((tb, backbone_rx, "Red Troncal"))

            urban_cells = rec.get("urban_z16_cells", [])
            if urban_cells:
                u_boxes = cls._build_urban_cluster_boxes(urban_cells, s, n, w, e)
                for ub in u_boxes:
                    queries_to_run.append((ub, local_rx, "Calles Urbanas"))
            else:
                local_boxes = cls._build_tight_subboxes(s, n, w, e, rings, has_poly, max_step=0.65)
                for lb in local_boxes:
                    queries_to_run.append((lb, local_rx, "Calles Locales"))
        else:
            step_sz = 0.65 if area_deg2 > 0.5 else 1.20
            all_boxes = cls._build_tight_subboxes(s, n, w, e, rings, has_poly, max_step=step_sz)
            for ab in all_boxes:
                queries_to_run.append((ab, full_rx, "Red Vial"))

        if not queries_to_run:
            queries_to_run.append(((s, w, n, e), full_rx, "Red Vial"))

        total_chunks = max(1, len(queries_to_run))
        elements_by_id = {}
        total_rx_bytes = [0]
        t_dl_start = time.perf_counter()

        headers = {
            "User-Agent": "ExonedPCForge/3.0 (Streaming)",
            "Accept-Encoding": "gzip, deflate"
        }

        sess = requests.Session()

        def _stream_overpass_box(bbox_tuple, rx_str, lbl_kind, block_idx, depth=0):
            if cancel_check and cancel_check():
                return []
            if pause_check:
                pause_check()

            cs, cw, cn, ce = bbox_tuple
            bbox_str = f"{cs:.4f},{cw:.4f},{cn:.4f},{ce:.4f}"
            # Consulta ultraligera: solo geom y tags viales, con vaciado inmediato 'out geom qt;'
            query = f'[out:json][timeout:60][bbox:{bbox_str}];way["highway"~"{rx_str}"];out geom tags qt;'

            m_count = len(cls.OVERPASS_MIRRORS)
            for attempt in range(m_count):
                if cancel_check and cancel_check():
                    return []
                if pause_check:
                    pause_check()

                m_idx = (block_idx + attempt + depth) % m_count
                mirror_url = cls.OVERPASS_MIRRORS[m_idx]
                mirror_short = mirror_url.split("//")[1].split("/")[0]

                try:
                    t_req = time.perf_counter()
                    with sess.post(mirror_url, data={"data": query}, headers=headers, stream=True, timeout=(10, 55)) as r:
                        if r.status_code == 200:
                            raw_buf = bytearray()
                            last_ui_ping = 0.0
                            for chunk in r.iter_content(chunk_size=16384):
                                if cancel_check and cancel_check():
                                    return []
                                if chunk:
                                    raw_buf.extend(chunk)
                                    total_rx_bytes[0] += len(chunk)
                                    now_p = time.perf_counter()
                                    if now_p - last_ui_ping >= 0.25:
                                        last_ui_ping = now_p
                                        dt_all = max(0.2, now_p - t_dl_start)
                                        kbps = (total_rx_bytes[0] / 1024.0) / dt_all
                                        if kb_cb:
                                            kb_cb(kbps)
                                        # Avance suave dentro del bloque actual según los bytes que van llegando
                                        intra_frac = min(0.92, len(raw_buf) / 650000.0)
                                        cur_frac = 0.03 + 0.57 * ((block_idx + intra_frac) / float(total_chunks))
                                        rem_s = int(max(2.0, (0.60 - cur_frac) / max(0.002, (cur_frac - 0.03) / dt_all)))
                                        if progress_cb:
                                            progress_cb(
                                                cur_frac,
                                                rem_s,
                                                f"Bloque {block_idx + 1}/{total_chunks} ({lbl_kind}): Recibiendo {len(raw_buf)//1024:,} KB ({kbps:.0f} KB/s) [{mirror_short}]..."
                                            )

                            data_json = json.loads(raw_buf.decode("utf-8", errors="replace"))
                            return data_json.get("elements", [])
                        elif r.status_code in (429, 502, 503, 504):
                            if progress_cb:
                                progress_cb(
                                    0.03 + 0.57 * (block_idx / float(total_chunks)),
                                    15,
                                    f"Espejo {mirror_short} ocupado (HTTP {r.status_code}), cambiando a servidor de respaldo..."
                                )
                            time.sleep(0.8)
                except Exception:
                    if progress_cb:
                        progress_cb(
                            0.03 + 0.57 * (block_idx / float(total_chunks)),
                            15,
                            f"Tiempo agotado en {mirror_short}, cambiando de servidor..."
                        )
                    time.sleep(0.5)

            # Si los 3 espejos fallaron porque la caja es demasiado densa, subdividir en 2 mitades automáticamente
            if depth < 2 and ((cn - cs) > 0.12 or (ce - cw) > 0.12):
                if (cn - cs) >= (ce - cw):
                    mid_lat = (cs + cn) * 0.5
                    els1 = _stream_overpass_box((cs, cw, mid_lat, ce), rx_str, lbl_kind, block_idx, depth + 1)
                    els2 = _stream_overpass_box((mid_lat, cw, cn, ce), rx_str, lbl_kind, block_idx + 1, depth + 1)
                else:
                    mid_lon = (cw + ce) * 0.5
                    els1 = _stream_overpass_box((cs, cw, cn, mid_lon), rx_str, lbl_kind, block_idx, depth + 1)
                    els2 = _stream_overpass_box((cs, mid_lon, cn, ce), rx_str, lbl_kind, block_idx + 1, depth + 1)
                return els1 + els2

            return []

        try:
            for idx_b, (bbox_t, rx_s, lbl_k) in enumerate(queries_to_run):
                if cancel_check and cancel_check():
                    return 0, 0
                if pause_check:
                    pause_check()

                dt_now = max(0.2, time.perf_counter() - t_dl_start)
                base_frac = 0.03 + 0.57 * (idx_b / float(total_chunks))
                rate_b = idx_b / dt_now if idx_b > 0 else 0.25
                rem_est = int((total_chunks - idx_b) / max(0.05, rate_b)) + 5

                if progress_cb:
                    progress_cb(
                        base_frac,
                        rem_est,
                        f"Solicitando {lbl_k}: bloque {idx_b + 1}/{total_chunks} ({len(elements_by_id):,} calles acumuladas)..."
                    )

                chunk_els = _stream_overpass_box(bbox_t, rx_s, lbl_k, idx_b, depth=0)
                for el in chunk_els:
                    eid = el.get("id")
                    if eid is not None:
                        elements_by_id[eid] = el
                    else:
                        elements_by_id[len(elements_by_id)] = el

                done_frac = 0.03 + 0.57 * ((idx_b + 1) / float(total_chunks))
                dt_after = max(0.2, time.perf_counter() - t_dl_start)
                rate_after = (idx_b + 1) / dt_after
                rem_after = int((total_chunks - (idx_b + 1)) / max(0.05, rate_after)) + 4
                if progress_cb:
                    progress_cb(
                        done_frac,
                        rem_after,
                        f"Bloque {idx_b + 1}/{total_chunks} completado ({len(elements_by_id):,} calles descargadas | {total_rx_bytes[0]//1024:,} KB)..."
                    )
        finally:
            sess.close()

        if not elements_by_id or (cancel_check and cancel_check()):
            return 0, 0

        arterial_tags = {
            "motorway", "trunk", "primary", "secondary", "tertiary",
            "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"
        }
        arterial_ways = []
        arterial_node_keys = set()
        candidate_connector_ways = []

        sx_min = int((w + 180.0) / cls.CELL_DEG)
        sx_max = int((e + 180.0) / cls.CELL_DEG)
        sy_min = int((s + 90.0) / cls.CELL_DEG)
        sy_max = int((n + 90.0) / cls.CELL_DEG)

        cell_buckets = {}
        total_ways_raw = max(1, len(elements_by_id))

        for idx_el, el in enumerate(elements_by_id.values()):
            if (idx_el & 2047) == 0:
                if cancel_check and cancel_check():
                    return 0, 0
                if pause_check:
                    pause_check()
                if progress_cb and idx_el > 0:
                    frac_p = 0.60 + 0.12 * (idx_el / float(total_ways_raw))
                    progress_cb(frac_p, 5, f"Indexando geometría vial ({idx_el:,}/{total_ways_raw:,} calles)...")

            geom = el.get("geometry")
            if not geom or len(geom) < 2:
                continue
            raw_pts = [(float(p["lat"]), float(p["lon"])) for p in geom if "lat" in p and "lon" in p]
            if len(raw_pts) < 2:
                continue
            if has_poly and rings:
                mid_pt = raw_pts[len(raw_pts) // 2]
                if not is_point_in_any_ring(mid_pt[0], mid_pt[1], rings):
                    continue

            pts = cls._densify_way_points(raw_pts, 55.0)

            tags = el.get("tags", {})
            hw_type = tags.get("highway", "")
            ow_raw = str(tags.get("oneway", "no")).lower()
            junction_type = str(tags.get("junction", "")).lower()

            if ow_raw in ("yes", "1", "true"):
                oneway_mode = 1
            elif ow_raw in ("-1", "reverse"):
                oneway_mode = -1
            elif junction_type in ("roundabout", "circular") or hw_type == "motorway":
                oneway_mode = 1
            else:
                oneway_mode = 0

            way_tuple = (pts, oneway_mode)
            if hw_type in arterial_tags:
                arterial_ways.append(way_tuple)
                for (plat, plon) in raw_pts:
                    arterial_node_keys.add((round(plat, 5), round(plon, 5)))
            else:
                candidate_connector_ways.append((pts, raw_pts, oneway_mode, hw_type))

            lats = [p[0] for p in raw_pts]
            lons = [p[1] for p in raw_pts]
            w_s, w_n = min(lats), max(lats)
            w_w, w_e = min(lons), max(lons)

            c_sx0 = max(sx_min, int((w_w - cls.HALO_DEG + 180.0) / cls.CELL_DEG))
            c_sx1 = min(sx_max, int((w_e + cls.HALO_DEG + 180.0) / cls.CELL_DEG))
            c_sy0 = max(sy_min, int((w_s - cls.HALO_DEG + 90.0) / cls.CELL_DEG))
            c_sy1 = min(sy_max, int((w_n + cls.HALO_DEG + 90.0) / cls.CELL_DEG))

            for csx in range(c_sx0, c_sx1 + 1):
                for csy in range(c_sy0, c_sy1 + 1):
                    b_key = (csx, csy)
                    if b_key not in cell_buckets:
                        cell_buckets[b_key] = []
                    cell_buckets[b_key].append(way_tuple)

        for (pts, raw_pts, oneway_mode, hw_type) in candidate_connector_ways:
            touches = sum(1 for (plat, plon) in raw_pts if (round(plat, 5), round(plon, 5)) in arterial_node_keys)
            if touches >= 2 or (touches >= 1 and hw_type == "unclassified"):
                way_len_m = sum(
                    cls.fast_distance_m(raw_pts[i][0], raw_pts[i][1], raw_pts[i + 1][0], raw_pts[i + 1][1])
                    for i in range(len(raw_pts) - 1)
                )
                if touches >= 2 and way_len_m <= 650.0:
                    arterial_ways.append((pts, oneway_mode))
                elif hw_type == "unclassified" and way_len_m <= 2500.0:
                    arterial_ways.append((pts, oneway_mode))

        if progress_cb:
            progress_cb(0.73, 4, "Compilando red troncal ARTERIAL.HWY...")

        art_source = arterial_ways if arterial_ways else [
            wt for bucket in cell_buckets.values() for wt in bucket
        ]
        art_n, _ = cls.write_hwy_binary(arterial_path, art_source, bounds=None, precision_digits=5)

        compiled_sectors = 0
        total_buckets = max(1, len(cell_buckets))
        t_start_cells = time.perf_counter()

        for b_idx, ((sx, sy), bucket_ways) in enumerate(cell_buckets.items()):
            if (b_idx & 63) == 0:
                if cancel_check and cancel_check():
                    return art_n, compiled_sectors
                if pause_check:
                    pause_check()

            cell_w = sx * cls.CELL_DEG - 180.0 - cls.HALO_DEG
            cell_e = (sx + 1) * cls.CELL_DEG - 180.0 + cls.HALO_DEG
            cell_s = sy * cls.CELL_DEG - 90.0 - cls.HALO_DEG
            cell_n = (sy + 1) * cls.CELL_DEG - 90.0 + cls.HALO_DEG

            sec_file = sectors_dir / f"S_{sx}_{sy}.HWY"
            sn, se = cls.write_hwy_binary(
                sec_file,
                bucket_ways,
                bounds=(cell_s, cell_n, cell_w, cell_e),
                precision_digits=5
            )
            if sn > 0 and se > 0:
                compiled_sectors += 1

            if progress_cb and (b_idx % 35 == 0 or b_idx + 1 == total_buckets):
                elapsed_c = max(0.05, time.perf_counter() - t_start_cells)
                rate_c = (b_idx + 1) / elapsed_c
                rem_sec = int(max(0, total_buckets - (b_idx + 1)) / max(1.0, rate_c))
                frac = 0.75 + 0.25 * ((b_idx + 1) / float(total_buckets))
                progress_cb(
                    frac,
                    rem_sec,
                    f"Empacando sectores locales: {b_idx + 1:,}/{total_buckets:,} ({compiled_sectors:,} archivos .HWY)..."
                )

        if compiled_sectors > 0 or art_n > 0:
            try:
                (job_dir / "routes_complete.flag").write_text(str(max(1, compiled_sectors)), encoding="utf-8")
            except Exception:
                pass

        return art_n, compiled_sectors


# =============================================================================
# 5. GOBERNADOR DE ALTA VELOCIDAD + DESCARGADOR DE VENTANA CONTINUA
# =============================================================================
def deg2num(lat_deg: float, lon_deg: float, zoom: int):
    lat_deg = max(-85.0511, min(85.0511, lat_deg))
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, xtile)), max(0, min(n - 1, ytile))

def tile_y_to_lat(y: float, z: int) -> float:
    n = math.pi - (2.0 * math.pi * y) / float(1 << z)
    return math.degrees(math.atan(math.sinh(n)))

def tile_x_to_lon(x: float, z: int) -> float:
    return (x / float(1 << z)) * 360.0 - 180.0

if HAS_NUMBA:
    @njit(nogil=True, cache=True)
    def _numba_pip(lat: float, lon: float, poly_arr: np.ndarray) -> bool:
        n = poly_arr.shape[0]
        if n < 3:
            return False
        inside = False
        j = n - 1
        for i in range(n):
            yi, xi = poly_arr[i, 0], poly_arr[i, 1]
            yj, xj = poly_arr[j, 0], poly_arr[j, 1]
            if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

_RING_CACHE_ID = None
_RING_CACHE_DATA = []

def is_point_in_polygon(lat: float, lon: float, poly: list) -> bool:
    if len(poly) < 3:
        return False
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        yi, xi = poly[i][0], poly[i][1]
        yj, xj = poly[j][0], poly[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def is_point_in_any_ring(lat: float, lon: float, rings: list) -> bool:
    global _RING_CACHE_ID, _RING_CACHE_DATA
    if not rings:
        return True
    if HAS_NUMBA:
        if id(rings) != _RING_CACHE_ID:
            compiled = []
            for r in rings:
                if len(r) >= 3:
                    arr = np.asarray(r, dtype=np.float64)
                    compiled.append((arr[:, 0].min(), arr[:, 0].max(), arr[:, 1].min(), arr[:, 1].max(), arr))
            _RING_CACHE_DATA = compiled
            _RING_CACHE_ID = id(rings)
        for (min_lat, max_lat, min_lon, max_lon, arr) in _RING_CACHE_DATA:
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                if _numba_pip(lat, lon, arr):
                    return True
        return False

    for r in rings:
        if is_point_in_polygon(lat, lon, r):
            return True
    return False


class FourChannelAntiBanGovernor:
    def __init__(self, total_target_tps: float = 180.0):
        self.total_target_tps = max(20.0, float(total_target_tps))
        self._locks = [threading.Lock() for _ in range(4)]
        now = time.perf_counter()
        self._next_slot = [now, now, now, now]
        self.tarpit_active = False

    def set_target_tps(self, tps: float):
        self.total_target_tps = max(20.0, float(tps))

    def wait_for_mirror_slot(self, mirror_idx: int):
        if self.total_target_tps >= 180.0:
            return
        m = mirror_idx & 3
        per_mirror_tps = self.total_target_tps / 4.0
        with self._locks[m]:
            now = time.perf_counter()
            step = (1.0 / per_mirror_tps) * random.uniform(0.88, 1.12)
            if self._next_slot[m] <= now:
                self._next_slot[m] = now + step
                return
            wait_s = min(0.025, self._next_slot[m] - now)
            self._next_slot[m] = now + wait_s + step
        if wait_s > 0.002:
            time.sleep(wait_s)

    def report_mirror_latency(self, mirror_idx: int, elapsed_ms: float):
        pass


class PcForgeEngine:

    def __init__(self):
        self.lang = "es"
        self.state = "IDLE"
        self.wizard_step = 0
        self.active_recipe = None
        self.forge_session_id = 0

        I18N["es"].update({
            "btn_all_merge_keep": "1. COMBINAR TODOS EN LA SD (DEJAR COPIA EN PC)",
            "btn_all_merge_move": "2. COMBINAR TODOS EN LA SD (Y BORRAR DE PC)",
            "btn_all_direct_move": "3. MOVER TODOS SIN COMBINAR (Y BORRAR DE PC)",
            "btn_item_resume": "▶ CONTINUAR DESCARGA",
            "btn_item_add_routes": "+ DESCARGAR RUTAS (.HWY)",
            "btn_item_merge_keep": "COMBINAR EN SD (DEJAR EN PC)",
            "btn_item_merge_move": "COMBINAR EN SD (BORRAR DE PC)",
            "btn_item_direct_move": "MOVER SIN COMBINAR (BORRAR DE PC)",
            "btn_item_slim": "BORRAR SOLO Z15-Z20",
            "btn_item_del": "ELIMINAR DE PC",
        })
        for _lk in I18N:
            if "btn_item_add_routes" not in I18N[_lk]:
                I18N[_lk]["btn_item_add_routes"] = "+ DOWNLOAD ROUTES (.HWY)"

        drives = NetworkUtils.list_available_drives(self.lang)
        local_drives = [d["root"] for d in drives if not d["is_removable"]]
        rem_drives = [d["root"] for d in drives if d["is_removable"]]

        default_pc = local_drives[0] if local_drives else (drives[0]["root"] if drives else str(Path.home()))
        default_sd = rem_drives[0] if rem_drives else default_pc

        self.target_drive_root = default_pc
        self.sd_deploy_drive_root = default_sd

        _, fast_t, _ = NetworkUtils.get_hardware_thread_counts()
        self.worker_threads_count = int(fast_t)
        self.rate_governor = FourChannelAntiBanGovernor(total_target_tps=180.0)

        self.prep_countdown_seconds = 0
        self.active_elapsed_seconds = 0.0
        self._last_run_tick = 0.0
        self.eta_formatted = "--:--"
        self.elapsed_formatted = "00m 00s"

        self.completed_sectors = 0
        self.total_sectors = 0
        self.completed_clusters = 0
        self.total_clusters = 0

        self.disk_stage_progress = 0.0
        self.sd_merge_progress = 0.0
        self.sd_transfer_done = False

        self.gm_ok = 0
        self.carto_rescue = 0
        self.net_pauses = 0
        self.written_bytes = 0

        self.mirror_offset = 0
        self.consecutive_ban_strikes = 0
        self.circuit_breaker_until = 0.0
        self.mirror_cooldown_until = [0.0, 0.0, 0.0, 0.0]
        self.stop_requested = False
        self.routes_status_str = ""
        self.routes_progress = 0.0
        self.routes_kbps = 0.0
        self._routes_speed_history = deque(maxlen=24)

        self._speed_history = deque(maxlen=24)
        self.current_tps = 0.0
        self.last_live_decode_ts = 0.0

        self.cluster_confidence = {}
        self._synthetic_qoi_cache = {}

        self.live_samples = deque(maxlen=10)
        self.witness_samples = deque(maxlen=24)
        self.sample_seq = 0
        self._lock = threading.Lock()
        self._thread_local = threading.local()
        self.on_ui_refresh = None

    def tr(self, key: str):
        return I18N.get(self.lang, I18N["es"]).get(key, I18N["es"].get(key, key))

    def is_busy_transferring(self) -> bool:
        return self.state in ("PREPARING", "RUNNING", "PAUSED_NET", "WAITING_ROUTES", "FLUSHING_DISK", "MERGING_SD")

    @staticmethod
    def _format_mm_ss(seconds_val: int) -> str:
        seconds_val = max(0, int(seconds_val))
        h = seconds_val // 3600
        m = (seconds_val % 3600) // 60
        s = seconds_val % 60
        if h > 0:
            return f"{h:02d}h {m:02d}m {s:02d}s"
        return f"{m:02d}m {s:02d}s"

    def get_thread_session(self) -> requests.Session:
        sess = getattr(self._thread_local, "session", None)
        req_count = getattr(self._thread_local, "req_count", 0)
        if sess is None or req_count >= 600:
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass
            sess = self._create_fast_http_session()
            self._thread_local.session = sess
            self._thread_local.req_count = 0
        self._thread_local.req_count += 1
        return sess

    def get_vault_root(self) -> Path:
        p = Path(self.target_drive_root) / "EXOSYS_VAULT"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_master_map_root(self) -> Path:
        p = Path(self.sd_deploy_drive_root) / "MAP"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def auto_discover_recent_recipe_file(self) -> tuple:
        search_dirs = []
        home = Path.home()
        for sub in ("Downloads/EXOSYS_LINK", "Downloads", "Descargas/EXOSYS_LINK", "Descargas", "Desktop", "Escritorio"):
            p = home / sub
            if p.exists() and p.is_dir():
                search_dirs.append(p)

        for d in NetworkUtils.list_available_drives(self.lang):
            root_p = Path(d["root"])
            for sub in ("EXOSYS_LINK", "Download/EXOSYS_LINK", "Downloads/EXOSYS_LINK"):
                cand_p = root_p / sub
                if cand_p.exists() and cand_p.is_dir():
                    search_dirs.append(cand_p)

        candidates = []
        for sdir in search_dirs:
            try:
                for f in sdir.glob("*.json"):
                    if f.is_file() and (".exorecipe" in f.name.lower() or "vault_meta" in f.name.lower() or "exo" in f.name.lower()):
                        candidates.append((f.stat().st_mtime, f))
            except Exception:
                pass

        if not candidates:
            return False, "No se encontró ningún archivo .exorecipe.json en Descargas ni en memorias USB."

        candidates.sort(key=lambda x: x[0], reverse=True)
        newest_file = candidates[0][1]
        try:
            raw = newest_file.read_text(encoding="utf-8")
            self.load_recipe(json.loads(raw), jump_to_step_2=True)
            return True, str(newest_file)
        except Exception as ex:
            return False, str(ex)

    def load_recipe(self, recipe_dict: dict, jump_to_step_2: bool = True):
        if self.is_busy_transferring() or not isinstance(recipe_dict, dict):
            return
        if "recipe_json" in recipe_dict and isinstance(recipe_dict["recipe_json"], dict):
            recipe_dict = recipe_dict["recipe_json"]
        if "north" not in recipe_dict or "south" not in recipe_dict:
            return

        zooms = sorted(recipe_dict.get("selected_zooms", []))
        is_routes_only = recipe_dict.get("routes_only", False) or (
            len(zooms) == 0 and recipe_dict.get("include_routes", True)
        )
        if is_routes_only:
            recipe_dict["routes_only"] = True
            recipe_dict["include_routes"] = True
            recipe_dict["zooms_summary"] = "SOLO RUTAS .HWY"
        else:
            recipe_dict["zooms_summary"] = f"Z{zooms[0]}-Z{zooms[-1]}" if zooms else "Z?"

        self.active_recipe = recipe_dict
        self.active_elapsed_seconds = 0.0
        self.elapsed_formatted = "00m 00s"
        self.eta_formatted = "--:--"
        self.completed_sectors = 0
        self.total_sectors = 0
        self.sd_transfer_done = False
        self.routes_progress = 0.0
        self.routes_kbps = 0.0
        self._routes_speed_history.clear()
        self.routes_status_str = ""
        self.disk_stage_progress = 0.0

        if jump_to_step_2 and self.wizard_step >= 1:
            self.wizard_step = 2
        if self.on_ui_refresh:
            self.on_ui_refresh()

    @staticmethod
    def _create_fast_http_session() -> requests.Session:
        s = requests.Session()
        adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=0)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s

    def run_fire_test_4_tiles(self, callback):
        if not self.active_recipe:
            callback(False, self.tr("lock_toast_no_order"), [])
            return

        def _worker():
            try:
                self.circuit_breaker_until = 0.0
                self.consecutive_ban_strikes = 0
                self.mirror_cooldown_until = [0.0, 0.0, 0.0, 0.0]
                rec = self.active_recipe
                c_lat = (rec["north"] + rec["south"]) * 0.5
                c_lon = (rec["east"] + rec["west"]) * 0.5

                cells = rec.get("urban_z16_cells", [])
                if cells:
                    mid_cell = cells[len(cells) // 2]
                    c_lat = tile_y_to_lat(mid_cell[1] + 0.5, 16)
                    c_lon = tile_x_to_lon(mid_cell[0] + 0.5, 16)

                zooms = sorted(rec.get("selected_zooms", [12, 16])) or [12, 16]
                max_z = zooms[-1]
                mid_z = (zooms[0] + max_z) // 2

                cx_max, cy_max = deg2num(c_lat, c_lon, max_z)
                cx_mid, cy_mid = deg2num(c_lat, c_lon, mid_z)

                coords = [
                    (mid_z, cx_mid, cy_mid),
                    (max_z, cx_max, cy_max),
                    (max_z, cx_max + 1, cy_max),
                    (max_z, cx_max, cy_max + 1),
                ]

                session = self._create_fast_http_session()
                results = []
                for (z, x, y) in coords:
                    res = self._fetch_and_process_tile(session, rec, z, x, y, force_decode_preview=True)
                    if not res:
                        callback(False, f"Z{z}/{x}/{y}", [])
                        return
                    results.append(res[0])
                callback(True, self.tr("fire_ok"), results)
            except Exception as ex:
                callback(False, str(ex), [])

        threading.Thread(target=_worker, daemon=True).start()

    def deploy_jobs_to_sd_map(self, job_ids: list, mode: str = "MERGE_KEEP"):
        if self.is_busy_transferring():
            return

        vault_root = self.get_vault_root()
        sd_root = Path(self.sd_deploy_drive_root)

        all_qois = []
        all_hwys = []
        valid_jdirs = []
        last_rec_meta = None

        for jid in job_ids:
            jdir = vault_root / jid
            if jdir.exists() and jdir.is_dir():
                valid_jdirs.append(jdir)
                meta_f = jdir / "vault_meta.json"
                if meta_f.exists():
                    try:
                        m_obj = json.loads(meta_f.read_text(encoding="utf-8"))
                        if isinstance(m_obj.get("recipe_json"), dict):
                            last_rec_meta = m_obj["recipe_json"]
                    except Exception:
                        pass
                self._audit_and_heal_hierarchy_on_folder(jdir, last_rec_meta or self.active_recipe or {})
                all_qois.extend(sorted(list(jdir.rglob("C_*_*.QOI"))))
                art_f = jdir / "ARTERIAL.HWY"
                if art_f.exists():
                    all_hwys.append(("ARTERIAL", art_f))
                sec_dir = jdir / "SECTORS"
                if sec_dir.exists():
                    for sf in sorted(sec_dir.glob("S_*_*.HWY")):
                        all_hwys.append(("SECTOR", sf))

        if not all_qois and not all_hwys:
            if self.on_ui_refresh:
                self.on_ui_refresh()
            return

        def _deploy_worker():
            try:
                self.state = "MERGING_SD"
                self.sd_transfer_done = False
                dst_map_root = self.get_master_map_root()
                dst_map_root.mkdir(parents=True, exist_ok=True)
                sd_sectors_root = sd_root / "SECTORS"

                total_items = max(1, len(all_qois) + len(all_hwys))
                done_items = 0

                for src_qoi in all_qois:
                    z_name = src_qoi.parent.name
                    if not z_name.startswith("Z"):
                        continue
                    dst_z_dir = dst_map_root / z_name
                    dst_z_dir.mkdir(parents=True, exist_ok=True)
                    dst_qoi = dst_z_dir / src_qoi.name

                    if mode == "DIRECT_MOVE":
                        shutil.copy2(src_qoi, dst_qoi)
                    else:
                        ClusterStorageHelper.merge_two_cluster_files(src_qoi, dst_qoi)

                    done_items += 1
                    self.sd_merge_progress = (done_items / float(total_items)) * 0.90
                    if self.on_ui_refresh and (done_items % 6 == 0 or done_items == total_items):
                        self.on_ui_refresh()

                for (kind, src_hwy) in all_hwys:
                    if kind == "ARTERIAL":
                        dst_hwy = sd_root / "ARTERIAL.HWY"
                    else:
                        sd_sectors_root.mkdir(parents=True, exist_ok=True)
                        dst_hwy = sd_sectors_root / src_hwy.name

                    if mode == "DIRECT_MOVE":
                        shutil.copy2(src_hwy, dst_hwy)
                    else:
                        HwyGraphCompilerPy.merge_two_hwy_files(src_hwy, dst_hwy)

                    done_items += 1
                    self.sd_merge_progress = (done_items / float(total_items)) * 0.90
                    if self.on_ui_refresh and (done_items % 12 == 0 or done_items == total_items):
                        self.on_ui_refresh()

                self._audit_and_heal_hierarchy_on_folder(dst_map_root, last_rec_meta or self.active_recipe or {})

                if mode in ("MERGE_MOVE", "DIRECT_MOVE"):
                    for jdir in valid_jdirs:
                        try:
                            shutil.rmtree(jdir, ignore_errors=True)
                        except Exception:
                            pass

                self.state = "COMPLETED"
                self.sd_merge_progress = 1.0
                self.sd_transfer_done = True
                if self.on_ui_refresh:
                    self.on_ui_refresh()
            except Exception:
                self.state = "IDLE"
                if self.on_ui_refresh:
                    self.on_ui_refresh()

        threading.Thread(target=_deploy_worker, daemon=True).start()

    def pause_forge_user(self):
        if self.state in ("RUNNING", "PREPARING", "PAUSED_NET", "WAITING_ROUTES"):
            self.state = "PAUSED_USER"
            if self.on_ui_refresh:
                self.on_ui_refresh()

    def _get_dark_void_rgb_tuple(self, style_idx: int) -> tuple:
        if style_idx == 5:
            return (0, 15, 0)
        elif style_idx == 2:
            return (18, 4, 16)
        elif style_idx == 1:
            return (3, 16, 26)
        return (8, 10, 12)

    def _get_dark_void_qoi(self, style_idx: int) -> bytes:
        with self._lock:
            if style_idx not in self._synthetic_qoi_cache:
                bg_rgb = self._get_dark_void_rgb_tuple(style_idx)
                synth_arr = np.empty((256, 256, 3), dtype=np.uint8)
                synth_arr[:, :, 0] = bg_rgb[0]
                synth_arr[:, :, 1] = bg_rgb[1]
                synth_arr[:, :, 2] = bg_rgb[2]
                self._synthetic_qoi_cache[style_idx] = QoiBinaryCodecPy.encode_rgb_array_to_qoi565(synth_arr)
            return self._synthetic_qoi_cache[style_idx]

    @staticmethod
    def _decode_qoi565_to_rgb_array(qoi_data: bytes) -> np.ndarray:
        w, h = 256, 256
        total_px = w * h
        rgb_out = bytearray(total_px * 3)
        cache = [0] * 64
        in_idx = 0
        out_idx = 0
        prev_px = 0
        comp_len = len(qoi_data)

        while in_idx < comp_len and out_idx < total_px:
            op = qoi_data[in_idx]
            in_idx += 1
            tag = op & 0xC0
            if tag == 0x00:
                run = (op & 0x3F) + 1
                r8 = ((prev_px >> 11) & 0x1F) << 3
                g8 = ((prev_px >> 5) & 0x3F) << 2
                b8 = (prev_px & 0x1F) << 3
                for _ in range(run):
                    if out_idx < total_px:
                        b_off = out_idx * 3
                        rgb_out[b_off] = r8
                        rgb_out[b_off + 1] = g8
                        rgb_out[b_off + 2] = b8
                        out_idx += 1
            elif tag == 0x40:
                px = cache[op & 0x3F]
                prev_px = px
                if out_idx < total_px:
                    b_off = out_idx * 3
                    rgb_out[b_off] = ((px >> 11) & 0x1F) << 3
                    rgb_out[b_off + 1] = ((px >> 5) & 0x3F) << 2
                    rgb_out[b_off + 2] = (px & 0x1F) << 3
                    out_idx += 1
            elif op == 0x80:
                if in_idx + 1 >= comp_len:
                    break
                px = qoi_data[in_idx] | (qoi_data[in_idx + 1] << 8)
                in_idx += 2
                cache[(px ^ (px >> 3)) & 63] = px
                prev_px = px
                if out_idx < total_px:
                    b_off = out_idx * 3
                    rgb_out[b_off] = ((px >> 11) & 0x1F) << 3
                    rgb_out[b_off + 1] = ((px >> 5) & 0x3F) << 2
                    rgb_out[b_off + 2] = (px & 0x1F) << 3
                    out_idx += 1

        return np.frombuffer(rgb_out, dtype=np.uint8).reshape((h, w, 3)).copy()

    @staticmethod
    def _read_single_tile_from_cluster(qoi_path: Path, tx: int, ty: int):
        if not qoi_path.exists():
            return None
        try:
            idx = ClusterStorageHelper.calc_local_idx(tx, ty)
            with open(qoi_path, "rb") as f:
                f.seek(idx * 8)
                ptr_bytes = f.read(8)
                if len(ptr_bytes) < 8:
                    return None
                off, length = struct.unpack("<II", ptr_bytes)
                if off < ClusterStorageHelper.HEADER_SIZE or length <= 20:
                    return None
                f.seek(off)
                data = f.read(length)
                return data if len(data) == length else None
        except Exception:
            return None

    @staticmethod
    def _write_single_tile_into_cluster(qoi_path: Path, tx: int, ty: int, tile_qoi_bytes: bytes):
        qoi_path.parent.mkdir(parents=True, exist_ok=True)
        hdr, pay = ClusterStorageHelper.load_existing_cluster_into_ram(qoi_path)
        idx = ClusterStorageHelper.calc_local_idx(tx, ty)
        write_off = ClusterStorageHelper.HEADER_SIZE + len(pay)
        struct.pack_into("<II", hdr, idx * 8, write_off, len(tile_qoi_bytes))
        pay.extend(tile_qoi_bytes)
        ClusterStorageHelper.atomic_save_cluster(qoi_path, hdr, pay)

    def _synthesize_parent_from_children_on_disk(self, root_dir: Path, z_parent: int, px: int, py: int, style_idx: int):
        z_child = z_parent + 1
        child_dir = root_dir / f"Z{z_child}"
        if not child_dir.exists():
            return None

        bg_rgb = self._get_dark_void_rgb_tuple(style_idx)
        canvas_512 = np.empty((512, 512, 3), dtype=np.uint8)
        canvas_512[:, :, 0] = bg_rgb[0]
        canvas_512[:, :, 1] = bg_rgb[1]
        canvas_512[:, :, 2] = bg_rgb[2]
        found_any = False

        for dx in (0, 1):
            for dy in (0, 1):
                cx_t = (px << 1) + dx
                cy_t = (py << 1) + dy
                c_file = child_dir / f"C_{cx_t // 32}_{cy_t // 32}.QOI"
                c_bytes = self._read_single_tile_from_cluster(c_file, cx_t, cy_t)
                if c_bytes is not None:
                    rgb_256 = self._decode_qoi565_to_rgb_array(c_bytes)
                    y0, x0 = dy * 256, dx * 256
                    canvas_512[y0:y0 + 256, x0:x0 + 256, :] = rgb_256
                    found_any = True

        if not found_any:
            return None

        down_256 = canvas_512.reshape(256, 2, 256, 2, 3).mean(axis=(1, 3)).astype(np.uint8)
        down_256[:, :, 0] = (down_256[:, :, 0] >> 3) << 3
        down_256[:, :, 1] = (down_256[:, :, 1] >> 2) << 2
        down_256[:, :, 2] = (down_256[:, :, 2] >> 3) << 3
        return QoiBinaryCodecPy.encode_rgb_array_to_qoi565(down_256)

    def _audit_and_heal_hierarchy_on_folder(self, root_dir: Path, rec: dict) -> int:
        if not root_dir.exists():
            return 0

        existing_z = []
        for d in root_dir.iterdir():
            if d.is_dir() and d.name.startswith("Z") and d.name[1:].isdigit():
                existing_z.append(int(d.name[1:]))

        rec_zooms = rec.get("selected_zooms", []) if isinstance(rec, dict) else []
        all_zooms = sorted(set(existing_z) | set(rec_zooms))
        if len(all_zooms) < 2:
            return 0

        z_min, z_max = all_zooms[0], all_zooms[-1]
        style_idx = rec.get("style_idx", 5) if isinstance(rec, dict) else 5
        effective_rec = dict(rec) if isinstance(rec, dict) else {}
        effective_rec.setdefault("style_idx", style_idx)
        effective_rec.setdefault("provider_idx", 0)

        sess = self._create_fast_http_session()
        healed_count = 0

        for z_hi in range(z_max, z_min, -1):
            if self.stop_requested:
                break
            z_lo = z_hi - 1
            z_hi_dir = root_dir / f"Z{z_hi}"
            z_lo_dir = root_dir / f"Z{z_lo}"
            if not z_hi_dir.exists():
                continue
            z_lo_dir.mkdir(parents=True, exist_ok=True)

            required_parents = set()
            for qf_hi in z_hi_dir.glob("C_*_*.QOI"):
                parts = qf_hi.stem.split("_")
                if len(parts) != 3:
                    continue
                try:
                    cx_hi, cy_hi = int(parts[1]), int(parts[2])
                except ValueError:
                    continue
                valid_slots = ClusterStorageHelper.inspect_existing_cluster(qf_hi)
                for slot in valid_slots:
                    tx_hi = cx_hi * 32 + (slot // 32)
                    ty_hi = cy_hi * 32 + (slot % 32)
                    required_parents.add((tx_hi >> 1, ty_hi >> 1))

            if not required_parents:
                continue

            parents_by_cluster = {}
            for (px, py) in required_parents:
                pcx, pcy = px // 32, py // 32
                if (pcx, pcy) not in parents_by_cluster:
                    parents_by_cluster[(pcx, pcy)] = []
                parents_by_cluster[(pcx, pcy)].append((px, py))

            for (pcx, pcy), p_coords in parents_by_cluster.items():
                p_file = z_lo_dir / f"C_{pcx}_{pcy}.QOI"
                existing_p = ClusterStorageHelper.inspect_existing_cluster(p_file)
                missing_p = [
                    (px, py) for (px, py) in p_coords
                    if ClusterStorageHelper.calc_local_idx(px, py) not in existing_p
                ]
                if not missing_p:
                    continue

                hdr, pay = ClusterStorageHelper.load_existing_cluster_into_ram(p_file)
                write_off = ClusterStorageHelper.HEADER_SIZE + len(pay)
                modified_cluster = False

                for (px, py) in missing_p:
                    if self.stop_requested:
                        break
                    qoi_p = None
                    res_p = self._fetch_and_process_tile(
                        sess, effective_rec, z_lo, px, py,
                        force_decode_preview=False,
                        allow_synthetic_404=False
                    )
                    if res_p is not None:
                        qoi_p = res_p[1]

                    if qoi_p is None:
                        qoi_p = self._synthesize_parent_from_children_on_disk(root_dir, z_lo, px, py, style_idx)

                    if qoi_p is None:
                        qoi_p = self._get_dark_void_qoi(style_idx)

                    if qoi_p is not None:
                        idx_slot = ClusterStorageHelper.calc_local_idx(px, py)
                        struct.pack_into("<II", hdr, idx_slot * 8, write_off, len(qoi_p))
                        pay.extend(qoi_p)
                        write_off += len(qoi_p)
                        modified_cluster = True
                        healed_count += 1

                if modified_cluster:
                    ClusterStorageHelper.atomic_save_cluster(p_file, hdr, pay)

        return healed_count

    def start_or_resume_forge(self, force_routes_only: bool = False):
        if self.state in ("PREPARING", "RUNNING", "WAITING_ROUTES", "FLUSHING_DISK", "MERGING_SD") or not self.active_recipe:
            return

        self.wizard_step = 3

        if self.state == "PAUSED_USER" and not force_routes_only and not self.stop_requested:
            is_r_only = getattr(self, "running_routes_only_pass", False)
            if (is_r_only and 0.0 < self.routes_progress < 1.0) or (self.total_sectors > 0 and self.completed_sectors < self.total_sectors):
                self._last_run_tick = time.perf_counter()
                self.state = "RUNNING"
                if self.on_ui_refresh:
                    self.on_ui_refresh()
                return

        rec = dict(self.active_recipe)
        is_routes_only = force_routes_only or rec.get("routes_only", False) or (
            len(rec.get("selected_zooms", [])) == 0 and rec.get("include_routes", True)
        )
        self.running_routes_only_pass = bool(is_routes_only)

        self.forge_session_id += 1
        my_session_id = self.forge_session_id

        self.stop_requested = False
        self.state = "PREPARING"
        self.prep_countdown_seconds = 3
        self.circuit_breaker_until = 0.0
        self.consecutive_ban_strikes = 0
        self.mirror_cooldown_until = [0.0, 0.0, 0.0, 0.0]
        self.cluster_confidence.clear()
        self._speed_history.clear()
        self._routes_speed_history.clear()
        self.current_tps = 0.0
        self.routes_kbps = 0.0
        self._last_run_tick = time.perf_counter()

        job_id = rec.get("job_id", "EXOSYS_JOB")
        job_dir = self.get_vault_root() / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        if not is_routes_only:
            self._save_vault_meta(job_dir, rec, "FORJANDO", self.completed_sectors)

        def _is_cancelled():
            return self.stop_requested or (self.forge_session_id != my_session_id)

        def _wait_if_paused():
            while self.state == "PAUSED_USER" and not _is_cancelled():
                time.sleep(0.2)

        def _master():
            try:
                self.routes_status_str = "1. RED VIAL (.HWY): Iniciando motor..."
                self.routes_progress = 0.0
                routes_done_event = threading.Event()

                if is_routes_only or rec.get("include_routes", True):
                    art_file = job_dir / "ARTERIAL.HWY"
                    sec_dir = job_dir / "SECTORS"
                    flag_file = job_dir / "routes_complete.flag"
                    existing_secs = len(list(sec_dir.glob("S_*_*.HWY"))) if sec_dir.exists() else 0

                    need_routes_build = (
                        is_routes_only or
                        not art_file.exists() or
                        art_file.stat().st_size < 100 or
                        existing_secs == 0 or
                        not flag_file.exists()
                    )

                    if need_routes_build:
                        def _route_worker():
                            if is_routes_only:
                                self.state = "RUNNING"
                                self.total_sectors = 0
                                self.completed_sectors = 0
                                self._last_run_tick = time.perf_counter()
                                self._routes_speed_history.append((time.perf_counter(), 0.0))

                            def _on_kb_rate(kbps_val):
                                self.routes_kbps = kbps_val

                            def _hwy_prog(frac_val, rem_s, status_txt=""):
                                if _is_cancelled():
                                    return
                                self.routes_progress = max(self.routes_progress, min(0.99, float(frac_val)))
                                pct_disp = self.routes_progress * 100.0
                                if status_txt:
                                    self.routes_status_str = f"1. RED VIAL ({pct_disp:.1f}%): {status_txt}"
                                else:
                                    self.routes_status_str = f"1. RED VIAL: Compilando... ({pct_disp:.1f}%)"

                                if is_routes_only:
                                    self.disk_stage_progress = self.routes_progress
                                if self.on_ui_refresh:
                                    self.on_ui_refresh()

                            art_n, sec_n = HwyGraphCompilerPy.compile_osm_hierarchy(
                                rec,
                                job_dir,
                                progress_cb=_hwy_prog,
                                cancel_check=_is_cancelled,
                                pause_check=_wait_if_paused,
                                kb_cb=_on_kb_rate
                            )

                            if _is_cancelled():
                                if self.forge_session_id == my_session_id:
                                    self.state = "PAUSED_USER"
                                    if self.on_ui_refresh:
                                        self.on_ui_refresh()
                                routes_done_event.set()
                                return

                            if art_n > 0 or sec_n > 0:
                                sz = art_file.stat().st_size if art_file.exists() else 0
                                sz_str = f"{sz/1024:.1f} KB" if sz < 1048576 else f"{sz/1048576:.2f} MB"
                                self.routes_status_str = f"1. RED VIAL LISTA: ARTERIAL ({sz_str}) + {sec_n:,} Sectores Urbanos (.HWY)"
                                self.routes_progress = 1.0
                                routes_done_event.set()
                                if is_routes_only and self.forge_session_id == my_session_id:
                                    self.state = "COMPLETED"
                                    self.eta_formatted = "00m 00s"
                                    self.disk_stage_progress = 1.0
                                    self._save_vault_meta(job_dir, rec, "COMPLETADO", 0)
                            else:
                                self.routes_status_str = "⚠ ERROR DE RED VIAL: Overpass no entregó calles. Pulsa INICIAR para reintentar."
                                self.routes_progress = 0.0
                                routes_done_event.set()
                                if is_routes_only and self.forge_session_id == my_session_id:
                                    self.state = "PAUSED_NET"
                                    self.eta_formatted = "--:--"

                            if self.on_ui_refresh:
                                self.on_ui_refresh()

                        if is_routes_only:
                            _route_worker()
                            return
                        else:
                            self.routes_status_str = "1. RED VIAL (0.0%): Descargando calles en segundo plano..."
                            threading.Thread(target=_route_worker, daemon=True).start()
                    else:
                        sz = art_file.stat().st_size if art_file.exists() else 0
                        sz_str = f"{sz/1024:.1f} KB" if sz < 1048576 else f"{sz/1048576:.2f} MB"
                        self.routes_status_str = f"1. RED VIAL YA GUARDADA: ARTERIAL ({sz_str}) + {existing_secs:,} Sectores (.HWY)"
                        self.routes_progress = 1.0
                        routes_done_event.set()
                else:
                    self.routes_status_str = "1. RED VIAL: No solicitada en este pedido"
                    self.routes_progress = 1.0
                    routes_done_event.set()

                self.prep_countdown_seconds = 3
                if self.on_ui_refresh:
                    self.on_ui_refresh()

                clusters_dict = self._build_pending_clusters_dict(rec)
                total_candidate_clusters = max(1, sum(len(c_map) for c_map in clusters_dict.values()))

                tasks_to_run = []
                already_done_count = 0
                already_done_clusters = 0
                existing_bytes = 0
                inspected_so_far = 0
                t0_audit = time.perf_counter()

                for z, clusters_in_z in clusters_dict.items():
                    if _is_cancelled():
                        return
                    z_dir = job_dir / f"Z{z}"
                    z_dir.mkdir(exist_ok=True)
                    for (cx, cy), expected_tiles in clusters_in_z.items():
                        inspected_so_far += 1
                        out_filepath = z_dir / f"C_{cx}_{cy}.QOI"
                        written_indices = ClusterStorageHelper.inspect_existing_cluster(out_filepath)
                        if out_filepath.exists():
                            existing_bytes += out_filepath.stat().st_size

                        missing_tiles = []
                        for (tx, ty) in expected_tiles:
                            l_idx = ClusterStorageHelper.calc_local_idx(tx, ty)
                            if l_idx in written_indices:
                                already_done_count += 1
                            else:
                                missing_tiles.append((tx, ty))

                        if missing_tiles:
                            tasks_to_run.append((z, cx, cy, missing_tiles))
                        else:
                            already_done_clusters += 1

                        if inspected_so_far % 40 == 0 or inspected_so_far == total_candidate_clusters:
                            dt_a = max(0.05, time.perf_counter() - t0_audit)
                            rate_a = inspected_so_far / dt_a
                            rem_a = int(max(0, total_candidate_clusters - inspected_so_far) / max(1.0, rate_a))
                            self.prep_countdown_seconds = rem_a
                            self.disk_stage_progress = inspected_so_far / float(total_candidate_clusters)
                            if self.on_ui_refresh:
                                self.on_ui_refresh()

                self.total_sectors = sum(len(t[3]) for t in tasks_to_run) + already_done_count
                self.completed_sectors = already_done_count
                self.total_clusters = len(tasks_to_run) + already_done_clusters
                self.completed_clusters = already_done_clusters
                self.written_bytes = existing_bytes

                if len(tasks_to_run) == 0:
                    if not routes_done_event.is_set():
                        self.state = "WAITING_ROUTES"
                        if self.on_ui_refresh:
                            self.on_ui_refresh()
                        routes_done_event.wait()
                    if not _is_cancelled():
                        self._run_final_disk_verification_pass(job_dir, rec, clusters_dict)
                    return

                self.state = "RUNNING"
                self.prep_countdown_seconds = 0
                self._last_run_tick = time.perf_counter()
                self._speed_history.append((time.perf_counter(), self.completed_sectors))
                if self.on_ui_refresh:
                    self.on_ui_refresh()

                fmt_pair = "<II"

                def _fetch_single_sector_job(z_val: int, tx_val: int, ty_val: int):
                    attempt = 0
                    cx, cy = tx_val // 32, ty_val // 32
                    cci_key = (z_val, cx, cy)

                    while not _is_cancelled():
                        _wait_if_paused()
                        if _is_cancelled():
                            return tx_val, ty_val, None

                        if self.state == "PAUSED_NET":
                            if NetworkUtils.check_internet_ping_ms() >= 0:
                                self.state = "RUNNING"
                                self._last_run_tick = time.perf_counter()
                            else:
                                time.sleep(1.0)
                                continue

                        now_ts = time.perf_counter()
                        need_live_preview = (now_ts - self.last_live_decode_ts) >= 0.65
                        if need_live_preview:
                            self.last_live_decode_ts = now_ts

                        sess = self.get_thread_session()
                        res = self._fetch_and_process_tile(sess, rec, z_val, tx_val, ty_val, force_decode_preview=need_live_preview)

                        if res is not None:
                            return tx_val, ty_val, res

                        attempt += 1

                        with self._lock:
                            cci = self.cluster_confidence.get(cci_key, {'hits': 0, 'misses': 0})
                            hits = cci['hits']
                            misses = cci['misses']

                        if z_val <= 16 or hits >= misses or (hits + misses) < 4:
                            max_attempts = 8
                        else:
                            max_attempts = 4

                        if attempt >= max_attempts:
                            return tx_val, ty_val, None

                        time.sleep(min(1.2, 0.20 * attempt))

                    return tx_val, ty_val, None

                num_workers = max(16, min(48, int(self.worker_threads_count)))
                max_in_flight_tiles = num_workers * 10

                with ThreadPoolExecutor(max_workers=num_workers) as tile_pool, ThreadPoolExecutor(max_workers=2) as disk_pool:
                    c_idx = 0
                    total_c_tasks = len(tasks_to_run)
                    cluster_buffers = {}
                    future_to_cluster = {}
                    disk_futures = []

                    def _flush_cluster_async(filepath_obj, hdr_bytes, pay_bytes):
                        try:
                            ClusterStorageHelper.atomic_save_cluster(filepath_obj, hdr_bytes, pay_bytes)
                        except Exception:
                            pass

                    while (c_idx < total_c_tasks or len(future_to_cluster) > 0) and not _is_cancelled():
                        while c_idx < total_c_tasks and len(future_to_cluster) < max_in_flight_tiles and not _is_cancelled():
                            z, cx, cy, tiles_in_cluster = tasks_to_run[c_idx]
                            c_idx += 1
                            out_filepath = job_dir / f"Z{z}" / f"C_{cx}_{cy}.QOI"
                            hdr, pay = ClusterStorageHelper.load_existing_cluster_into_ram(out_filepath)
                            cluster_buffers[(z, cx, cy)] = [
                                out_filepath, hdr, pay,
                                ClusterStorageHelper.HEADER_SIZE + len(pay),
                                0, len(tiles_in_cluster)
                            ]
                            for (tx, ty) in tiles_in_cluster:
                                fut = tile_pool.submit(_fetch_single_sector_job, z, tx, ty)
                                future_to_cluster[fut] = (z, cx, cy)

                        if not future_to_cluster:
                            break

                        done_futs, _ = wait(future_to_cluster.keys(), timeout=0.25, return_when=FIRST_COMPLETED)
                        for fut in done_futs:
                            z, cx, cy = future_to_cluster.pop(fut)
                            c_state = cluster_buffers.get((z, cx, cy))
                            if c_state is None:
                                continue

                            tx, ty, res = fut.result()
                            local_idx = ClusterStorageHelper.calc_local_idx(tx, ty)
                            c_state[5] -= 1

                            if res is not None:
                                sample_dict, qoi_bytes = res
                                data_len = len(qoi_bytes)
                                struct.pack_into(fmt_pair, c_state[1], local_idx * 8, c_state[3], data_len)
                                c_state[2].extend(qoi_bytes)
                                c_state[3] += data_len
                                c_state[4] += 1

                                with self._lock:
                                    self.written_bytes += data_len
                                    self.completed_sectors += 1
                                    done_now = self.completed_sectors

                                    if sample_dict is not None:
                                        self.sample_seq += 1
                                        self.live_samples.append(sample_dict)

                                    if done_now == 1 or done_now % 250 == 0:
                                        if sample_dict is None:
                                            b64_w = QoiBinaryCodecPy.decode_qoi_to_base64_png(qoi_bytes)
                                            sample_dict = {
                                                "z": z, "x": tx, "y": ty,
                                                "source": "GM",
                                                "kb": data_len / 1024.0,
                                                "b64": b64_w
                                            }
                                        self.sample_seq += 1
                                        self.witness_samples.append(sample_dict)

                                if done_now % 500 == 0:
                                    self._save_vault_meta(job_dir, rec, "FORJANDO", done_now)

                            if c_state[5] <= 0:
                                cluster_buffers.pop((z, cx, cy), None)
                                if c_state[4] > 0:
                                    df = disk_pool.submit(_flush_cluster_async, c_state[0], c_state[1], c_state[2])
                                    disk_futures.append(df)
                                with self._lock:
                                    self.completed_clusters += 1
                                    tot_c = max(1, self.total_clusters)
                                    self.disk_stage_progress = min(0.95, self.completed_clusters / float(tot_c))

                        disk_futures = [df for df in disk_futures if not df.done()]

                    for (z, cx, cy), c_state in list(cluster_buffers.items()):
                        if c_state[4] > 0:
                            df = disk_pool.submit(_flush_cluster_async, c_state[0], c_state[1], c_state[2])
                            disk_futures.append(df)
                    for df in disk_futures:
                        try:
                            df.result(timeout=10.0)
                        except Exception:
                            pass

                if _is_cancelled():
                    if self.forge_session_id == my_session_id:
                        self.state = "PAUSED_USER"
                        self.disk_stage_progress = 1.0
                        self._save_vault_meta(job_dir, rec, "PAUSADO", self.completed_sectors)
                        if self.on_ui_refresh:
                            self.on_ui_refresh()
                else:
                    if not routes_done_event.is_set():
                        self.state = "WAITING_ROUTES"
                        if self.on_ui_refresh:
                            self.on_ui_refresh()
                        routes_done_event.wait()

                    if not _is_cancelled():
                        self._run_final_disk_verification_pass(job_dir, rec, clusters_dict)

            except Exception:
                if self.forge_session_id == my_session_id:
                    self.state = "IDLE"
                    if self.on_ui_refresh:
                        self.on_ui_refresh()

        threading.Thread(target=_master, daemon=True).start()

    def _run_final_disk_verification_pass(self, job_dir: Path, rec: dict, clusters_dict=None):
        self.state = "FLUSHING_DISK"
        for tmp_f in job_dir.rglob("*.TMP"):
            try:
                tmp_f.unlink()
            except Exception:
                pass

        if not rec.get("routes_only", False):
            if clusters_dict:
                sess_rescue = self._create_fast_http_session()
                for z, clusters_in_z in sorted(clusters_dict.items(), reverse=True):
                    if self.stop_requested:
                        break
                    z_dir = job_dir / f"Z{z}"
                    for (cx, cy), expected_tiles in clusters_in_z.items():
                        if self.stop_requested:
                            break
                        q_path = z_dir / f"C_{cx}_{cy}.QOI"
                        written = ClusterStorageHelper.inspect_existing_cluster(q_path)
                        missing = [
                            (tx, ty) for (tx, ty) in expected_tiles
                            if ClusterStorageHelper.calc_local_idx(tx, ty) not in written
                        ]
                        if not missing:
                            continue
                        hdr, pay = ClusterStorageHelper.load_existing_cluster_into_ram(q_path)
                        w_off = ClusterStorageHelper.HEADER_SIZE + len(pay)
                        changed = False
                        for (tx, ty) in missing:
                            if self.stop_requested:
                                break
                            res_t = self._fetch_and_process_tile(sess_rescue, rec, z, tx, ty, force_decode_preview=False)
                            if res_t is not None:
                                q_bytes = res_t[1]
                                slot = ClusterStorageHelper.calc_local_idx(tx, ty)
                                struct.pack_into("<II", hdr, slot * 8, w_off, len(q_bytes))
                                pay.extend(q_bytes)
                                w_off += len(q_bytes)
                                changed = True
                                with self._lock:
                                    self.completed_sectors += 1
                        if changed:
                            ClusterStorageHelper.atomic_save_cluster(q_path, hdr, pay)

            healed = self._audit_and_heal_hierarchy_on_folder(job_dir, rec)
            if healed > 0:
                with self._lock:
                    self.completed_sectors += healed

        all_qois = sorted(list(job_dir.rglob("C_*_*.QOI")))
        tot_files = max(1, len(all_qois))
        actual_total_tiles = 0

        for idx, qf in enumerate(all_qois):
            slots = ClusterStorageHelper.inspect_existing_cluster(qf)
            actual_total_tiles += len(slots)
            self.disk_stage_progress = (idx + 1) / float(tot_files)
            if self.on_ui_refresh and (idx % 12 == 0 or idx + 1 == tot_files):
                self.on_ui_refresh()

        self.state = "COMPLETED"
        self.eta_formatted = "00m 00s"
        self.disk_stage_progress = 1.0
        if not rec.get("routes_only", False):
            self.completed_sectors = max(self.completed_sectors, actual_total_tiles)
            self.total_sectors = self.completed_sectors
            rec["estimated_tiles"] = self.completed_sectors
            self._save_vault_meta(job_dir, rec, "COMPLETADO", self.completed_sectors)
        if self.on_ui_refresh:
            self.on_ui_refresh()

    def update_telemetry_strings(self):
        now = time.perf_counter()
        if self.state in ("RUNNING", "WAITING_ROUTES", "FLUSHING_DISK"):
            if self._last_run_tick > 0:
                self.active_elapsed_seconds += max(0.0, now - self._last_run_tick)
            self._last_run_tick = now
            self.elapsed_formatted = self._format_mm_ss(int(self.active_elapsed_seconds))
        else:
            self._last_run_tick = now

        if self.state not in ("RUNNING", "WAITING_ROUTES") or not self.active_recipe:
            return

        # Si está en modo SOLO RUTAS o esperando que terminen las rutas, calcular ETA dinámico real segundo a segundo
        if getattr(self, "running_routes_only_pass", False) or self.active_recipe.get("routes_only", False) or self.state == "WAITING_ROUTES":
            prog = max(0.0, min(1.0, self.routes_progress))
            self._routes_speed_history.append((now, prog))
            if prog >= 0.995:
                self.eta_formatted = "00m 01s"
            elif prog > 0.035 and self.active_elapsed_seconds > 2.0:
                avg_rate = prog / max(1.0, self.active_elapsed_seconds)
                if len(self._routes_speed_history) >= 2:
                    t0, p0 = self._routes_speed_history[0]
                    win_rate = max(0.0, (prog - p0) / max(0.5, now - t0))
                    eff_rate = (avg_rate * 0.65) + (win_rate * 0.35)
                else:
                    eff_rate = avg_rate
                if eff_rate > 0.0002:
                    rem_s = int((1.0 - prog) / eff_rate)
                    self.eta_formatted = self._format_mm_ss(min(7200, max(1, rem_s)))
                else:
                    self.eta_formatted = "Calculando..."
            else:
                self.eta_formatted = "Calculando..."
            return

        done = self.completed_sectors
        self._speed_history.append((now, done))
        if len(self._speed_history) >= 2:
            t0, d0 = self._speed_history[0]
            dt = max(0.1, now - t0)
            window_tps = max(0.0, (done - d0) / dt)

            if getattr(self, "current_tps", 0.0) <= 0.1:
                self.current_tps = window_tps
            else:
                self.current_tps = (self.current_tps * 0.85) + (window_tps * 0.15)

        tot = max(1, self.total_sectors)
        rem_sectors = max(0, tot - done)
        if self.current_tps > 0.4:
            eta_sec = int(rem_sectors / self.current_tps)
            self.eta_formatted = self._format_mm_ss(eta_sec)
        else:
            self.eta_formatted = "..."

    def _resolve_ota_node(self, rec: dict) -> tuple:
        tpl = rec.get("primary_tile_template", "")
        ref = rec.get("primary_referer", "")
        if tpl and "{x}" in tpl:
            return tpl, (ref or "https://exosys.local/")
        if not hasattr(self, "_cached_ota_tpl"):
            self._cached_ota_tpl = ""
            self._cached_ota_ref = "https://exosys.local/"
            try:
                r = requests.get("https://theexoned.github.io/config.json", timeout=5.0)
                if r.status_code == 200:
                    j = r.json()
                    if "tile_tpl_b64" in j:
                        self._cached_ota_tpl = base64.b64decode(j["tile_tpl_b64"]).decode("utf-8")
                    elif "tile_url" in j:
                        self._cached_ota_tpl = j["tile_url"]
                    if "referer_b64" in j:
                        self._cached_ota_ref = base64.b64decode(j["referer_b64"]).decode("utf-8")
                    elif "referer" in j:
                        self._cached_ota_ref = j["referer"]
            except Exception:
                pass
        return self._cached_ota_tpl, self._cached_ota_ref

    def _fetch_and_process_tile(
        self,
        session: requests.Session,
        rec: dict,
        z: int,
        x: int,
        y: int,
        force_decode_preview: bool = False,
        allow_synthetic_404: bool = True
    ):
        pil_img = None
        source_tag = "GM"

        tile_tpl, primary_ref = self._resolve_ota_node(rec)
        headers_g = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Referer": primary_ref
        }

        style_idx = rec.get("style_idx", 0)
        scale_param = 2 if style_idx in (0, 1, 2, 5) else 1
        now_t = time.time()
        try_primary = (rec.get("provider_idx", 0) == 0)

        network_error_flag = False
        cx, cy = x // 32, y // 32
        cci_key = (z, cx, cy)

        if try_primary and tile_tpl:
            lyrs = "y" if style_idx == 3 else "m"
            base_m = (x + y + self.mirror_offset) & 3

            for m_step in range(4):
                m_cur = (base_m + m_step) & 3
                if m_step == 0 and now_t < self.mirror_cooldown_until[m_cur]:
                    continue
                self.rate_governor.wait_for_mirror_slot(m_cur)

                url_g = (
                    tile_tpl
                    .replace("{s}", str(m_cur))
                    .replace("{type}", lyrs)
                    .replace("{lyrs}", lyrs)
                    .replace("{x}", str(x))
                    .replace("{y}", str(y))
                    .replace("{z}", str(z))
                )
                if "scale=" not in url_g:
                    url_g += f"&scale={scale_param}&hl=es"

                code_g, bytes_g = self._http_get(session, url_g, headers_g)

                if code_g == 200 and bytes_g:
                    pil_img = TileAuditorPy.decode_and_audit(bytes_g, allow_hi_res_512=(scale_param == 2))
                    if pil_img is not None:
                        break

                if code_g == 404:
                    break
                else:
                    network_error_flag = True
                    if code_g in (-1, 403, 429, 503):
                        self.mirror_cooldown_until[m_cur] = now_t + 2.5
                        with self._lock:
                            self.mirror_offset = (self.mirror_offset + 1) & 3

            if pil_img is not None:
                with self._lock:
                    self.consecutive_ban_strikes = 0
                    self.gm_ok += 1

        if pil_img is None:
            source_tag = "CARTO"
            sub_idx = (x + y) % 3
            self.rate_governor.wait_for_mirror_slot(sub_idx)
            sub = ("a", "b", "c")[sub_idx]
            api_key = rec.get("carto_api_key", "")
            q_key = f"?api_key={urllib.parse.quote(api_key)}" if api_key else ""
            c_url = f"https://{sub}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png{q_key}"
            code_c, c_bytes = self._http_get(session, c_url, {"Referer": "https://carto.com/"})

            if code_c == 200 and c_bytes:
                pil_img = TileAuditorPy.decode_and_audit(c_bytes, allow_hi_res_512=False)
                if pil_img is not None and TileAuditorPy.is_carto_watermark(pil_img):
                    pil_img = None

            if pil_img is None and code_c != 404:
                network_error_flag = True

            if pil_img is not None:
                with self._lock:
                    self.carto_rescue += 1
            elif rec.get("provider_idx", 0) != 0:
                source_tag = "ESRI"
                eb_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
                code_eb, eb_bytes = self._http_get(session, eb_url, {"Referer": "https://www.arcgis.com/"})

                if code_eb == 200 and eb_bytes:
                    base_img = TileAuditorPy.decode_and_audit(eb_bytes, allow_hi_res_512=False)
                    if base_img is not None:
                        el_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
                        _, el_bytes = self._http_get(session, el_url, {"Referer": "https://www.arcgis.com/"})
                        lbl_img = TileAuditorPy.decode_and_audit(el_bytes, allow_hi_res_512=False)
                        if lbl_img is not None:
                            base_img.paste(lbl_img, (0, 0))
                        pil_img = base_img
                        with self._lock:
                            self.carto_rescue += 1

                if pil_img is None and code_eb != 404:
                    network_error_flag = True

        if pil_img is None:
            if network_error_flag or not allow_synthetic_404:
                return None
            with self._lock:
                if cci_key not in self.cluster_confidence:
                    self.cluster_confidence[cci_key] = {'hits': 0, 'misses': 0}
                self.cluster_confidence[cci_key]['misses'] += 1

            source_tag = "SINTÉTICA (404)"
            qoi_bytes = self._get_dark_void_qoi(style_idx)

            sample_info = None
            if force_decode_preview:
                b64_preview = QoiBinaryCodecPy.decode_qoi_to_base64_png(qoi_bytes)
                if b64_preview:
                    sample_info = {
                        "z": z, "x": x, "y": y,
                        "source": source_tag,
                        "kb": len(qoi_bytes) / 1024.0,
                        "b64": b64_preview
                    }
            return sample_info, qoi_bytes

        with self._lock:
            if cci_key not in self.cluster_confidence:
                self.cluster_confidence[cci_key] = {'hits': 0, 'misses': 0}
            self.cluster_confidence[cci_key]['hits'] += 1

        rgb_arr = np.asarray(pil_img, dtype=np.uint8)
        if source_tag == "GM" and style_idx in (0, 1, 2, 5):
            shaded_arr = CyberpunkShaderEnginePy.apply_shader_to_rgb_array(rgb_arr, style_idx)
        elif style_idx == 5:
            shaded_arr = CyberpunkShaderEnginePy.apply_shader_to_rgb_array(rgb_arr, 5)
        else:
            if rgb_arr.shape[0] != 256 or rgb_arr.shape[1] != 256:
                pil_256 = pil_img.resize((256, 256), Image.Resampling.BILINEAR)
                shaded_arr = np.asarray(pil_256, dtype=np.uint8)
            else:
                shaded_arr = rgb_arr

        qoi_bytes = QoiBinaryCodecPy.encode_rgb_array_to_qoi565(shaded_arr)

        sample_info = None
        if force_decode_preview:
            b64_preview = QoiBinaryCodecPy.decode_qoi_to_base64_png(qoi_bytes)
            if b64_preview:
                sample_info = {
                    "z": z, "x": x, "y": y,
                    "source": source_tag,
                    "kb": len(qoi_bytes) / 1024.0,
                    "b64": b64_preview
                }
        return sample_info, qoi_bytes

    @staticmethod
    def _http_get(session: requests.Session, url: str, headers: dict):
        try:
            r = session.get(url, headers=headers, timeout=(2.0, 2.8))
            return r.status_code, (r.content if r.status_code == 200 else None)
        except Exception:
            return -1, None

    @staticmethod
    def _build_pending_clusters_dict(rec: dict):
        selected_zooms = sorted(rec.get("selected_zooms", []))
        if not selected_zooms:
            return {}

        isolate = rec.get("isolate_urban_high_zoom", True)
        raw_cells = rec.get("urban_z16_cells", [])
        has_mask = isolate and len(raw_cells) > 0
        z16_set = set((c[0], c[1]) for c in raw_cells)

        has_poly = rec.get("has_custom_polygon", False)
        rings = rec.get("selection_rings", [])

        tiles_by_z = {z: set() for z in selected_zooms}

        for z in selected_zooms:
            x0, y0 = deg2num(rec["north"], rec["west"], z)
            x1, y1 = deg2num(rec["south"], rec["east"], z)
            min_x, max_x = min(x0, x1), max(x0, x1)
            min_y, max_y = min(y0, y1), max(y0, y1)

            if has_mask and z >= 15:
                if z == 15:
                    for (cx16, cy16) in z16_set:
                        tx, ty = cx16 >> 1, cy16 >> 1
                        if min_x <= tx <= max_x and min_y <= ty <= max_y:
                            tiles_by_z[z].add((tx, ty))
                elif z == 16:
                    for (cx16, cy16) in z16_set:
                        if min_x <= cx16 <= max_x and min_y <= cy16 <= max_y:
                            tiles_by_z[z].add((cx16, cy16))
                else:
                    shift = z - 16
                    span = 1 << shift
                    for (cx16, cy16) in z16_set:
                        base_x = cx16 << shift
                        base_y = cy16 << shift
                        for dx in range(span):
                            tx = base_x + dx
                            if not (min_x <= tx <= max_x):
                                continue
                            for dy in range(span):
                                ty = base_y + dy
                                if min_y <= ty <= max_y:
                                    tiles_by_z[z].add((tx, ty))
            else:
                for tx in range(min_x, max_x + 1):
                    for ty in range(min_y, max_y + 1):
                        if has_poly and rings:
                            lat_c = tile_y_to_lat(ty + 0.5, z)
                            lon_c = tile_x_to_lon(tx + 0.5, z)
                            if not is_point_in_any_ring(lat_c, lon_c, rings):
                                continue
                        tiles_by_z[z].add((tx, ty))

        for idx_hi in range(len(selected_zooms) - 1, 0, -1):
            z_hi = selected_zooms[idx_hi]
            z_lo = selected_zooms[idx_hi - 1]
            shift = z_hi - z_lo
            parent_set = tiles_by_z[z_lo]
            for (tx, ty) in tiles_by_z[z_hi]:
                parent_set.add((tx >> shift, ty >> shift))

        clusters = {}
        for z in selected_zooms:
            clusters[z] = {}
            for (tx, ty) in sorted(tiles_by_z[z]):
                cx, cy = tx // 32, ty // 32
                if (cx, cy) not in clusters[z]:
                    clusters[z][(cx, cy)] = []
                clusters[z][(cx, cy)].append((tx, ty))

        return clusters

    @staticmethod
    def _save_vault_meta(job_dir: Path, rec: dict, status: str, completed_tiles: int):
        try:
            s_idx = rec.get("style_idx", 0)
            style_name = (
                "Nocturno V1" if s_idx == 0 else
                "Arasaka V2" if s_idx == 1 else
                "Kiroshi V3" if s_idx == 2 else
                "Pip-Boy V4" if s_idx == 5 else
                "Satelital" if s_idx == 3 else "Clásico"
            )
            zooms = sorted(rec.get("selected_zooms", []))
            z_summary = "SOLO RUTAS .HWY" if (rec.get("routes_only", False) or len(zooms) == 0) else f"Z{zooms[0]}-Z{zooms[-1]}"
            meta = {
                "job_id": rec.get("job_id"),
                "job_name": rec.get("job_name"),
                "style_name": style_name,
                "zooms_summary": z_summary,
                "completed_tiles": completed_tiles,
                "total_tiles": rec.get("estimated_tiles", 0),
                "status": status,
                "recipe_json": rec
            }
            (job_dir / "vault_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except Exception:
            pass

    def list_pc_vault_maps(self) -> list:
        root = self.get_vault_root()
        out = []
        is_removable = False
        for d in NetworkUtils.list_available_drives(self.lang):
            if str(root).upper().startswith(d["root"].upper()):
                is_removable = d["is_removable"]
                break

        for folder in root.iterdir():
            if not folder.is_dir():
                continue
            meta_f = folder / "vault_meta.json"
            j_name = folder.name
            style_name = "Mapa"
            z_sum = ""
            comp = 0
            tot = 0
            status = "COMPLETADO"
            rec_obj = None

            if meta_f.exists():
                try:
                    m = json.loads(meta_f.read_text(encoding="utf-8"))
                    j_name = m.get("job_name", j_name)
                    style_name = m.get("style_name", style_name)
                    z_sum = m.get("zooms_summary", z_sum)
                    comp = m.get("completed_tiles", 0)
                    tot = m.get("total_tiles", 0)
                    status = m.get("status", status)
                    rec_obj = m.get("recipe_json")
                except Exception:
                    pass

            size_b = 0
            art_p = folder / "ARTERIAL.HWY"
            if art_p.exists():
                size_b += art_p.stat().st_size
            sec_dir = folder / "SECTORS"
            sec_count = 0
            if sec_dir.exists():
                with os.scandir(sec_dir) as it:
                    for entry in it:
                        if entry.is_file() and entry.name.endswith(".HWY"):
                            size_b += entry.stat().st_size
                            sec_count += 1
            qoi_count = 0
            for z in range(6, 21):
                z_dir = folder / f"Z{z}"
                if z_dir.exists():
                    with os.scandir(z_dir) as it:
                        for entry in it:
                            if entry.is_file() and entry.name.endswith(".QOI"):
                                size_b += entry.stat().st_size
                                qoi_count += 1

            has_high = any((folder / f"Z{z}").exists() for z in range(15, 21))
            has_hwy = art_p.exists() and sec_count > 0

            if status == "FORJANDO" and tot > 0 and comp >= tot:
                status = "COMPLETADO"
            if qoi_count == 0 and not has_hwy and size_b == 0:
                status = "PENDIENTE (0 MB)"

            out.append({
                "job_id": folder.name,
                "job_name": j_name,
                "source": "PC_SD" if is_removable else "PC_DISK",
                "style_name": style_name,
                "zooms_summary": z_sum,
                "completed_tiles": comp,
                "total_tiles": tot,
                "size_mb": round(size_b / (1024 ** 2), 2),
                "status": status,
                "has_high_res": has_high,
                "has_hwy": has_hwy,
                "sec_count": sec_count,
                "qoi_count": qoi_count,
                "folder_path": str(folder),
                "recipe_json": rec_obj
            })
        return sorted(out, key=lambda x: x["size_mb"], reverse=True)

    def delete_or_prune_map(self, job_id: str, prune_high_res_only: bool):
        folder = self.get_vault_root() / job_id
        if not folder.exists():
            return
        if prune_high_res_only:
            for z in range(15, 21):
                zf = folder / f"Z{z}"
                if zf.exists():
                    shutil.rmtree(zf, ignore_errors=True)
        else:
            shutil.rmtree(folder, ignore_errors=True)


ENGINE = PcForgeEngine()
SERVER_PIN = "2077"

# =============================================================================
# 6. SERVIDOR HTTP PUERTO 8890
# =============================================================================
class ExosysLinkHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def _check_pin(self) -> bool:
        client_pin = self.headers.get("X-Exosys-Pin", "").strip()
        return (not SERVER_PIN) or (client_pin == SERVER_PIN)

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"EXOSYS_PC_FORGE_ONLINE")
            return

        if not self._check_pin():
            self.send_response(403)
            self.end_headers()
            return

        if self.path.startswith("/api/vault_list"):
            maps = ENGINE.list_pc_vault_maps()
            clean_maps = [{k: v for k, v in m.items() if k != "recipe_json"} for m in maps]
            payload = json.dumps({"status": "OK", "maps": clean_maps}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"EXOSYS_PC_FORGE_ONLINE")

    def do_POST(self):
        if not self._check_pin():
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"PIN_INCORRECTO")
            return

        if self.path.startswith("/api/submit_job"):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8")
            try:
                recipe_obj = json.loads(raw)
                ENGINE.load_recipe(recipe_obj, jump_to_step_2=True)
                if recipe_obj.get("auto_start", False):
                    ENGINE.start_or_resume_forge()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ORDEN_RECIBIDA_EN_PC")
            except Exception as ex:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(ex).encode("utf-8"))

        elif self.path.startswith("/api/vault_delete"):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            job_id = qs.get("job_id", [""])[0]
            mode = qs.get("mode", ["delete_all"])[0]
            if job_id:
                ENGINE.delete_or_prune_map(job_id, prune_high_res_only=(mode == "prune_high_res"))
                if ENGINE.on_ui_refresh:
                    ENGINE.on_ui_refresh()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")


def start_http_server():
    try:
        server = ThreadingHTTPServer(("0.0.0.0", 8890), ExosysLinkHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    except Exception as ex:
        print(f"[WARN] Puerto 8890 ocupado: {ex}")


# =============================================================================
# 7. INTERFAZ SECUENCIAL MULTILENGUAJE (PASOS 0 A 4 — CERO ERRORWIDGET GRIS)
# =============================================================================
C_BG = "#02080A"
C_PANEL = "#0A1114"
C_CARD = "#061418"
C_CYAN = "#00E5FF"
C_GREEN = "#00FF41"
C_AMBER = "#FFB300"
C_DARK = "#061A1E"
C_CRIT = "#FF003C"
C_LOCKED_BG = "#0B1012"
C_LOCKED_BORDER = "#1F292E"
C_LOCKED_TEXT = "#4A5A60"

def main(page: ft.Page):
    page.title = "EXOSYS"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = C_BG
    page.padding = 14
    page.window_width = 1240
    page.window_height = 860

    safe_t, fast_t, turbo_t = NetworkUtils.get_hardware_thread_counts()

    def show_edge_case_lock_toast(msg: str):
        page.snack_bar = ft.SnackBar(
            bgcolor=C_CRIT,
            content=ft.Text(msg, color="#FFFFFF", weight=ft.FontWeight.BOLD, size=13)
        )
        page.snack_bar.open = True
        page.update()

    def can_navigate_to_phase(target_step: int) -> tuple:
        if target_step == ENGINE.wizard_step:
            return True, ""
        if ENGINE.is_busy_transferring():
            return False, ENGINE.tr("lock_toast_busy")
        if target_step in (2, 3) and ENGINE.active_recipe is None:
            return False, ENGINE.tr("lock_toast_no_order")
        return True, ""

    def switch_wizard_phase(target_step: int):
        ok, reason = can_navigate_to_phase(target_step)
        if not ok:
            show_edge_case_lock_toast(reason)
            return
        ENGINE.wizard_step = target_step
        if target_step == 2:
            update_disk_audit_label()
        sync_ui_from_engine(refresh_vault=(target_step == 4))

    def select_language_and_advance(lang_code: str):
        if ENGINE.is_busy_transferring():
            return
        ENGINE.lang = lang_code
        apply_language_to_all_static_widgets()
        ENGINE.wizard_step = 2 if ENGINE.active_recipe is not None else 1
        sync_ui_from_engine(refresh_vault=False)

    # -------------------------------------------------------------------------
    # PASO 0: SELECTOR DE IDIOMA
    # -------------------------------------------------------------------------
    txt_s0_title = ft.Text(ENGINE.tr("step0_title"), color=C_CYAN, size=22, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    txt_s0_sub = ft.Text(ENGINE.tr("step0_sub"), color="#CCCCCC", size=14, text_align=ft.TextAlign.CENTER)

    lang_cards_spec = [
        ("es", "Español", "Asistente paso a paso en español"),
        ("en", "English", "Step-by-step assistant in English"),
        ("zh", "中文 (简体)", "中文分步安装向导"),
        ("ja", "日本語", "日本語ステップバイステップ案内"),
        ("hi", "हिन्दी", "हिंदी में आसान चरण-दर-चरण मार्गदर्शिका"),
        ("fr", "Français", "Assistant étape par étape en français"),
        ("ar", "العربية", "مساعد خطوة بخطوة باللغة العربية"),
        ("ru", "Русский", "Пошаговый помощник на русском языке"),
    ]

    lang_cards_row = ft.Row(spacing=14, run_spacing=14, alignment=ft.MainAxisAlignment.CENTER, wrap=True)
    for l_code, l_native, l_desc in lang_cards_spec:
        def _make_lang_click(c):
            def _h(e):
                select_language_and_advance(c)
            return _h

        card = ft.Container(
            width=265,
            height=115,
            bgcolor=C_CARD,
            padding=14,
            border_radius=10,
            border=ft.border.all(2, C_CYAN),
            ink=True,
            on_click=_make_lang_click(l_code),
            alignment=ft.alignment.center,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
                controls=[
                    ft.Text(l_native, color=C_GREEN, size=22, weight=ft.FontWeight.BOLD),
                    ft.Text(l_desc, color="#CCCCCC", size=11.5, text_align=ft.TextAlign.CENTER),
                ]
            )
        )
        lang_cards_row.controls.append(card)

    view_phase_0 = ft.Container(
        visible=True,
        expand=True,
        bgcolor=C_PANEL,
        padding=26,
        border_radius=8,
        border=ft.border.all(1, C_CYAN),
        alignment=ft.alignment.center,
        content=ft.Column(
            spacing=22,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[txt_s0_title, txt_s0_sub, lang_cards_row]
        )
    )

    # -------------------------------------------------------------------------
    # PASO 1: CONECTAR CON EL TELÉFONO (GUÍA CLARA + AUTO-DETECTOR .JSON)
    # -------------------------------------------------------------------------
    info_ips = NetworkUtils.get_classified_ips()
    main_ip_val = info_ips["primary"]

    txt_s1_title = ft.Text("", color=C_CYAN, size=20, weight=ft.FontWeight.BOLD)
    txt_s1_sub = ft.Text("", color="#CCCCCC", size=13, text_align=ft.TextAlign.CENTER)
    txt_cred_box_title = ft.Text("", color=C_AMBER, size=12, weight=ft.FontWeight.BOLD)
    txt_ip_wifi_line = ft.Text("", color=C_GREEN, size=19, weight=ft.FontWeight.BOLD, font_family="Consolas")
    txt_ip_usb_line = ft.Text("", color=C_CYAN, size=13)

    txt_opt_a_title = ft.Text("", color=C_CYAN, weight=ft.FontWeight.BOLD, size=13)
    txt_opt_a_body = ft.Text("", color="#BBBBBB", size=12)
    txt_opt_b_title = ft.Text("", color=C_GREEN, weight=ft.FontWeight.BOLD, size=13)
    txt_opt_b_body = ft.Text("", color="#BBBBBB", size=12)
    txt_opt_c_title = ft.Text("", color=C_AMBER, weight=ft.FontWeight.BOLD, size=13)
    txt_opt_c_body = ft.Text("", color="#BBBBBB", size=12)

    def on_file_picked(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            fpath = e.files[0].path
            try:
                raw = Path(fpath).read_text(encoding="utf-8")
                ENGINE.load_recipe(json.loads(raw), jump_to_step_2=True)
            except Exception as ex:
                show_edge_case_lock_toast(f"Archivo inválido: {ex}")

    file_picker = ft.FilePicker(on_result=on_file_picked)
    page.overlay.append(file_picker)

    def on_auto_detect_json_click(e):
        ok, info_msg = ENGINE.auto_discover_recent_recipe_file()
        if not ok:
            show_edge_case_lock_toast(info_msg)

    btn_auto_json = ft.ElevatedButton(
        "⚡ DETECTAR .JSON AUTOMÁTICAMENTE (DESCARGAS / USB)",
        bgcolor=C_GREEN,
        color="#000000",
        on_click=on_auto_detect_json_click
    )
    btn_pick_file = ft.ElevatedButton(
        "",
        bgcolor=C_AMBER,
        color="#000000",
        on_click=lambda _: file_picker.pick_files(allowed_extensions=["json"])
    )
    txt_recipe_summary_s1 = ft.Text("", color=C_AMBER, size=14, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    txt_recipe_summary_s2 = ft.Text("", color=C_GREEN, size=14, weight=ft.FontWeight.BOLD)

    btn_to_step2 = ft.ElevatedButton("", bgcolor=C_GREEN, color="#000000", on_click=lambda _: switch_wizard_phase(2))
    btn_to_step4_direct = ft.ElevatedButton("", bgcolor=C_DARK, color=C_CYAN, on_click=lambda _: switch_wizard_phase(4))

    view_phase_1 = ft.Container(
        visible=False,
        expand=True,
        bgcolor=C_PANEL,
        padding=24,
        border_radius=8,
        border=ft.border.all(1, C_CYAN),
        content=ft.Column(
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                txt_s1_title,
                txt_s1_sub,
                ft.Container(
                    bgcolor=C_CARD,
                    padding=16,
                    border_radius=8,
                    border=ft.border.all(2, C_GREEN),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[txt_cred_box_title, txt_ip_wifi_line, txt_ip_usb_line]
                    )
                ),
                ft.Row(
                    spacing=14,
                    alignment=ft.MainAxisAlignment.CENTER,
                    wrap=True,
                    controls=[
                        ft.Container(
                            width=360, bgcolor=C_CARD, padding=14, border_radius=6, border=ft.border.all(1, C_CYAN),
                            content=ft.Column(spacing=6, controls=[txt_opt_a_title, txt_opt_a_body])
                        ),
                        ft.Container(
                            width=360, bgcolor=C_CARD, padding=14, border_radius=6, border=ft.border.all(1, C_GREEN),
                            content=ft.Column(spacing=6, controls=[txt_opt_b_title, txt_opt_b_body])
                        ),
                        ft.Container(
                            width=380, bgcolor=C_CARD, padding=14, border_radius=6, border=ft.border.all(1, C_AMBER),
                            content=ft.Column(spacing=8, controls=[txt_opt_c_title, txt_opt_c_body, btn_auto_json, btn_pick_file])
                        ),
                    ]
                ),
                ft.Container(bgcolor=C_CARD, padding=12, border_radius=6, border=ft.border.all(1, C_DARK), content=txt_recipe_summary_s1),
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=14,
                    controls=[btn_to_step2, btn_to_step4_direct]
                )
            ]
        )
    )

    # -------------------------------------------------------------------------
    # PASO 2 Y 2.1: SELECCIÓN DE DISCO, ESTILO VISUAL (PIP-BOY) Y VISTA PREVIA
    # -------------------------------------------------------------------------
    txt_s2_title = ft.Text("", color=C_CYAN, size=20, weight=ft.FontWeight.BOLD)
    txt_disk_audit_s2 = ft.Text("", color=C_GREEN, size=14, weight=ft.FontWeight.BOLD)
    txt_disk_audit_s4 = ft.Text("", color=C_GREEN, size=14, weight=ft.FontWeight.BOLD)

    def update_disk_audit_label():
        try:
            usage_pc = shutil.disk_usage(ENGINE.target_drive_root)
            free_pc_gb = usage_pc.free / (1024 ** 3)
            free_pc_mb = usage_pc.free / (1024 ** 2)
            usage_sd = shutil.disk_usage(ENGINE.sd_deploy_drive_root)
            free_sd_gb = usage_sd.free / (1024 ** 3)

            req_mb = ENGINE.active_recipe.get("estimated_weight_mb", 0.0) if ENGINE.active_recipe else 0.0
            if req_mb > 0:
                fits = free_pc_mb >= req_mb
                txt_disk_audit_s2.color = C_GREEN if fits else C_CRIT
                tpl = ENGINE.tr("space_ok") if fits else ENGINE.tr("space_low")
                txt_disk_audit_s2.value = tpl.format(pc_gb=free_pc_gb, req_mb=req_mb)
            else:
                txt_disk_audit_s2.color = C_GREEN
                txt_disk_audit_s2.value = ENGINE.tr("space_idle").format(pc_gb=free_pc_gb, sd_gb=free_sd_gb)

            txt_disk_audit_s4.color = C_GREEN
            txt_disk_audit_s4.value = ENGINE.tr("space_idle").format(pc_gb=free_pc_gb, sd_gb=free_sd_gb)
        except Exception:
            pass

    def on_vault_drive_change(e):
        if ENGINE.is_busy_transferring():
            dd_drives.value = ENGINE.target_drive_root
            show_edge_case_lock_toast(ENGINE.tr("lock_toast_busy"))
            return
        ENGINE.target_drive_root = dd_drives.value
        update_disk_audit_label()
        refresh_vault_column()
        page.update()

    def on_sd_drive_change(e):
        if ENGINE.is_busy_transferring():
            dd_sd_drive.value = ENGINE.sd_deploy_drive_root
            show_edge_case_lock_toast(ENGINE.tr("lock_toast_busy"))
            return
        ENGINE.sd_deploy_drive_root = dd_sd_drive.value
        update_disk_audit_label()
        refresh_vault_column()
        page.update()

    drives_list = NetworkUtils.list_available_drives(ENGINE.lang)

    dd_drives = ft.Dropdown(
        value=ENGINE.target_drive_root,
        width=520,
        options=[ft.dropdown.Option(key=d["root"], text=d["label"]) for d in drives_list],
        bgcolor=C_CARD,
        border_color=C_CYAN,
        color=C_CYAN,
        text_size=13,
        on_change=on_vault_drive_change
    )

    def on_style_override_change(e):
        if ENGINE.active_recipe is not None and not ENGINE.is_busy_transferring():
            val = int(dd_style_override.value)
            if val >= 0:
                ENGINE.active_recipe["style_idx"] = val

    dd_style_override = ft.Dropdown(
        label="Filtro / Estilo Visual del Mapa",
        value="-1",
        width=280,
        options=[
            ft.dropdown.Option("-1", "Usar estilo del pedido"),
            ft.dropdown.Option("0", "V1: Nocturno (Dark Standard)"),
            ft.dropdown.Option("1", "V2: Arasaka Grid (Cian/Rojo)"),
            ft.dropdown.Option("2", "V3: Kiroshi Optics (Magenta)"),
            ft.dropdown.Option("5", "V4: Pip-Boy 3000 CRT (Verde)"),
            ft.dropdown.Option("3", "Satelital Híbrido"),
            ft.dropdown.Option("4", "Clásico Día"),
        ],
        bgcolor=C_CARD,
        border_color=C_GREEN,
        color=C_GREEN,
        text_size=13,
        on_change=on_style_override_change
    )

    dd_sd_drive = ft.Dropdown(
        value=ENGINE.sd_deploy_drive_root,
        width=760,
        options=[ft.dropdown.Option(key=d["root"], text=d["label"]) for d in drives_list],
        bgcolor=C_CARD,
        border_color=C_GREEN,
        color=C_GREEN,
        text_size=13,
        on_change=on_sd_drive_change
    )

    def refresh_drives_and_vault(e=None):
        if ENGINE.is_busy_transferring():
            show_edge_case_lock_toast(ENGINE.tr("lock_toast_busy"))
            return
        new_drives = NetworkUtils.list_available_drives(ENGINE.lang)
        dd_drives.options = [ft.dropdown.Option(key=d["root"], text=d["label"]) for d in new_drives]
        dd_sd_drive.options = [ft.dropdown.Option(key=d["root"], text=d["label"]) for d in new_drives]

        rem = [d["root"] for d in new_drives if d["is_removable"]]
        if rem:
            ENGINE.sd_deploy_drive_root = rem[0]
            dd_sd_drive.value = rem[0]

        update_disk_audit_label()
        refresh_vault_column()
        page.update()

    btn_refresh_s2 = ft.ElevatedButton("", bgcolor=C_DARK, color=C_CYAN, on_click=refresh_drives_and_vault)
    btn_refresh_s4 = ft.ElevatedButton("", bgcolor=C_DARK, color=C_CYAN, on_click=refresh_drives_and_vault)

    txt_s2_1_title = ft.Text("", color=C_AMBER, size=15, weight=ft.FontWeight.BOLD)
    txt_fire_status = ft.Text("", color="#AAAAAA", size=12)
    row_fire_samples = ft.Row(spacing=12, wrap=True)

    def trigger_fire_test(e):
        txt_fire_status.value = ENGINE.tr("fire_testing")
        txt_fire_status.color = C_AMBER
        page.update()

        def _on_done(ok, msg, samples):
            txt_fire_status.value = msg
            txt_fire_status.color = C_GREEN if ok else C_CRIT
            row_fire_samples.controls.clear()
            for s in samples:
                row_fire_samples.controls.append(
                    ft.Container(
                        bgcolor=C_DARK,
                        padding=8,
                        border_radius=6,
                        border=ft.border.all(1, C_CYAN),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=4,
                            controls=[
                                ft.Image(src_base64=s["b64"], width=84, height=84),
                                ft.Text(f"Z{s['z']} ({s['kb']:.1f} KB)", size=11, color=C_CYAN)
                            ]
                        )
                    )
                )
            page.update()

        ENGINE.run_fire_test_4_tiles(_on_done)

    btn_fire_test = ft.ElevatedButton("", bgcolor=C_DARK, color=C_GREEN, on_click=trigger_fire_test)
    btn_back_s1 = ft.ElevatedButton("", bgcolor=C_DARK, color=C_CYAN, on_click=lambda _: switch_wizard_phase(1))
    btn_to_s3 = ft.ElevatedButton("", bgcolor=C_GREEN, color="#000000", on_click=lambda _: switch_wizard_phase(3))

    view_phase_2 = ft.Container(
        visible=False,
        expand=True,
        bgcolor=C_PANEL,
        padding=22,
        border_radius=8,
        border=ft.border.all(1, C_CYAN),
        content=ft.Column(
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                txt_s2_title,
                ft.Container(bgcolor=C_CARD, padding=12, border_radius=6, border=ft.border.all(1, C_GREEN), content=txt_recipe_summary_s2),
                ft.Row(spacing=10, wrap=True, controls=[dd_drives, dd_style_override, btn_refresh_s2]),
                txt_disk_audit_s2,
                ft.Divider(color=C_DARK),
                ft.Container(
                    bgcolor=C_CARD,
                    padding=16,
                    border_radius=8,
                    border=ft.border.all(1, C_AMBER),
                    content=ft.Column(
                        spacing=10,
                        controls=[txt_s2_1_title, txt_fire_status, row_fire_samples, ft.Row(controls=[btn_fire_test])]
                    )
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[btn_back_s1, btn_to_s3]
                )
            ]
        )
    )

    # -------------------------------------------------------------------------
    # PASO 3: DESCARGA Y VELOCIDAD EN VIVO
    # -------------------------------------------------------------------------
    txt_s3_title = ft.Text("", color=C_CYAN, size=19, weight=ft.FontWeight.BOLD)
    btn_go_phase4_from_3 = ft.ElevatedButton("", bgcolor=C_CYAN, color="#000000", visible=False, on_click=lambda _: switch_wizard_phase(4))

    txt_giant_state_title = ft.Text("", color=C_GREEN, size=24, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    txt_giant_state_sub = ft.Text("", color="#CCCCCC", size=13, text_align=ft.TextAlign.CENTER)
    giant_status_banner = ft.Container(
        bgcolor=C_CARD,
        padding=16,
        border_radius=8,
        border=ft.border.all(2, C_GREEN),
        alignment=ft.alignment.center,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
            controls=[txt_giant_state_title, txt_giant_state_sub]
        )
    )

    lbl_clock_active = ft.Text("", color="#999999", size=11, weight=ft.FontWeight.BOLD)
    lbl_clock_eta = ft.Text("", color="#999999", size=11, weight=ft.FontWeight.BOLD)
    lbl_clock_speed = ft.Text("", color="#999999", size=11, weight=ft.FontWeight.BOLD)

    txt_clock_elapsed = ft.Text("00m 00s", color=C_CYAN, size=22, weight=ft.FontWeight.BOLD, font_family="Consolas")
    txt_clock_eta = ft.Text("--:--", color=C_GREEN, size=22, weight=ft.FontWeight.BOLD, font_family="Consolas")
    txt_clock_speed = ft.Text("0.0 /s", color=C_AMBER, size=22, weight=ft.FontWeight.BOLD, font_family="Consolas")

    clocks_bar = ft.Row(
        spacing=12,
        controls=[
            ft.Container(
                expand=1, bgcolor=C_CARD, padding=12, border_radius=6, border=ft.border.all(1, C_DARK),
                content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, controls=[lbl_clock_active, txt_clock_elapsed])
            ),
            ft.Container(
                expand=1, bgcolor=C_CARD, padding=12, border_radius=6, border=ft.border.all(1, C_DARK),
                content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, controls=[lbl_clock_eta, txt_clock_eta])
            ),
            ft.Container(
                expand=1, bgcolor=C_CARD, padding=12, border_radius=6, border=ft.border.all(1, C_DARK),
                content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, controls=[lbl_clock_speed, txt_clock_speed])
            ),
        ]
    )

    def on_threads_change(e):
        ENGINE.worker_threads_count = int(dd_threads.value)

    dd_threads = ft.Dropdown(
        value=str(fast_t),
        width=220,
        bgcolor=C_CARD,
        border_color=C_CYAN,
        color=C_GREEN,
        text_size=12,
        on_change=on_threads_change
    )

    def on_rate_change(e):
        ENGINE.rate_governor.set_target_tps(float(dd_rate.value))

    dd_rate = ft.Dropdown(
        value="180",
        width=250,
        bgcolor=C_CARD,
        border_color=C_AMBER,
        color=C_AMBER,
        text_size=12,
        on_change=on_rate_change
    )

    btn_start_s3 = ft.ElevatedButton("", bgcolor=C_GREEN, color="#000000", on_click=lambda _: ENGINE.start_or_resume_forge())
    btn_pause_s3 = ft.ElevatedButton("", bgcolor=C_AMBER, color="#000000", on_click=lambda _: ENGINE.pause_forge_user())
    btn_stop_s3 = ft.ElevatedButton("", bgcolor=C_CRIT, color="#FFFFFF", on_click=lambda _: setattr(ENGINE, "stop_requested", True))

    lbl_pb_routes = ft.Text("1. RED VIAL Y CALLES (.HWY): Esperando inicio...", color=C_CYAN, size=12.5, weight=ft.FontWeight.BOLD)
    txt_pb_routes_pct = ft.Text("0.0%", color=C_CYAN, size=12, weight=ft.FontWeight.BOLD)
    pb_routes = ft.ProgressBar(value=0.0, color=C_CYAN, bgcolor=C_DARK, height=12)

    lbl_pb_tiles = ft.Text("2. IMÁGENES DEL MAPA (.QOI): Esperando inicio...", color=C_GREEN, size=12.5, weight=ft.FontWeight.BOLD)
    txt_pb_tiles_pct = ft.Text("0.0%", color=C_GREEN, size=12, weight=ft.FontWeight.BOLD)
    pb_main = ft.ProgressBar(value=0.0, color=C_GREEN, bgcolor=C_DARK, height=12)

    col_progress_bars = ft.Container(
        bgcolor=C_CARD,
        padding=12,
        border_radius=6,
        border=ft.border.all(1, C_DARK),
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[lbl_pb_routes, txt_pb_routes_pct]),
                pb_routes,
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[lbl_pb_tiles, txt_pb_tiles_pct]),
                pb_main
            ]
        )
    )

    lbl_live_strip = ft.Text("", color=C_AMBER, size=11, weight=ft.FontWeight.BOLD)
    lbl_witness_strip = ft.Text("", color=C_CYAN, size=11, weight=ft.FontWeight.BOLD)
    row_live_strip = ft.Row(spacing=8, scroll=ft.ScrollMode.AUTO)
    row_witness_strip = ft.Row(spacing=8, scroll=ft.ScrollMode.AUTO)

    view_phase_3 = ft.Container(
        visible=False,
        expand=True,
        bgcolor=C_PANEL,
        padding=20,
        border_radius=8,
        border=ft.border.all(1, C_CYAN),
        content=ft.Column(
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True, controls=[txt_s3_title, btn_go_phase4_from_3]),
                giant_status_banner,
                clocks_bar,
                ft.Row(
                    spacing=10,
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[btn_start_s3, btn_pause_s3, btn_stop_s3, dd_threads, dd_rate]
                ),
                col_progress_bars,
                ft.Row(
                    spacing=12,
                    controls=[
                        ft.Container(
                            expand=1, bgcolor=C_CARD, padding=10, border_radius=6, border=ft.border.all(1, C_DARK),
                            content=ft.Column(spacing=6, controls=[lbl_live_strip, ft.Container(height=105, content=row_live_strip)])
                        ),
                        ft.Container(
                            expand=1, bgcolor=C_CARD, padding=10, border_radius=6, border=ft.border.all(1, C_DARK),
                            content=ft.Column(spacing=6, controls=[lbl_witness_strip, ft.Container(height=105, content=row_witness_strip)])
                        ),
                    ]
                )
            ]
        )
    )

    # -------------------------------------------------------------------------
    # PASO 4: FUSIONAR O MOVER A LA MEMORIA
    # -------------------------------------------------------------------------
    txt_s4_title = ft.Text("", color=C_GREEN, size=20, weight=ft.FontWeight.BOLD)
    txt_s4_sub = ft.Text("", color="#CCCCCC", size=13)
    txt_sd_merge_notice = ft.Text("", color=C_CYAN, size=14, weight=ft.FontWeight.BOLD)
    pb_sd_merge = ft.ProgressBar(value=0.0, color=C_CYAN, bgcolor=C_DARK, height=10)
    box_sd_merge_notice = ft.Container(
        bgcolor=C_CARD,
        padding=12,
        border_radius=6,
        border=ft.border.all(1, C_CYAN),
        content=ft.Column(spacing=6, controls=[txt_sd_merge_notice, pb_sd_merge])
    )

    box_legend_step4 = ft.Container(
        bgcolor=C_CARD,
        padding=12,
        border_radius=6,
        border=ft.border.all(1, C_AMBER),
        content=ft.Column(
            spacing=4,
            controls=[
                ft.Text("GUÍA RÁPIDA DE BOTONES (PASO 4):", color=C_AMBER, size=12, weight=ft.FontWeight.BOLD),
                ft.Text("• COMBINAR EN SD (DEJAR EN PC): Une este mapa/ruta con lo que ya tenga tu MicroSD, y CONSERVA la copia en tu PC.", color=C_CYAN, size=11.5),
                ft.Text("• COMBINAR EN SD (BORRAR DE PC): Une este mapa/ruta con lo que ya tenga tu MicroSD, y al terminar LO BORRA de la PC.", color=C_GREEN, size=11.5),
                ft.Text("• MOVER SIN COMBINAR (BORRAR DE PC): Pasa los archivos directo encima de la MicroSD y LO BORRA de la PC.", color=C_AMBER, size=11.5),
            ]
        )
    )

    txt_mass_ops_title = ft.Text("", color=C_CYAN, size=13, weight=ft.FontWeight.BOLD)
    txt_single_ops_title = ft.Text("", color=C_AMBER, size=13, weight=ft.FontWeight.BOLD)

    def deploy_all_vault_maps(mode_str: str):
        maps = ENGINE.list_pc_vault_maps()
        jids = [m["job_id"] for m in maps]
        ENGINE.deploy_jobs_to_sd_map(jids, mode=mode_str)

    btn_global_merge_keep = ft.ElevatedButton("", bgcolor=C_CYAN, color="#000000", on_click=lambda _: deploy_all_vault_maps("MERGE_KEEP"))
    btn_global_merge_move = ft.ElevatedButton("", bgcolor=C_GREEN, color="#000000", on_click=lambda _: deploy_all_vault_maps("MERGE_MOVE"))
    btn_global_direct_move = ft.ElevatedButton("", bgcolor=C_AMBER, color="#000000", on_click=lambda _: deploy_all_vault_maps("DIRECT_MOVE"))

    col_vault_items = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=250)

    def refresh_vault_column():
        col_vault_items.controls.clear()
        maps = ENGINE.list_pc_vault_maps()
        busy_now = ENGINE.is_busy_transferring()

        if not maps:
            col_vault_items.controls.append(
                ft.Text(ENGINE.tr("no_maps_yet"), color="#888888", size=13)
            )
        for m in maps:
            jid = m["job_id"]
            rec_saved = m.get("recipe_json")

            def _make_resume(r_obj):
                def _h(e):
                    if r_obj and not ENGINE.is_busy_transferring():
                        ENGINE.load_recipe(r_obj, jump_to_step_2=False)
                        ENGINE.start_or_resume_forge(force_routes_only=False)
                return _h

            def _make_build_routes_only(r_obj):
                def _h(e):
                    if r_obj and not ENGINE.is_busy_transferring():
                        ENGINE.load_recipe(r_obj, jump_to_step_2=False)
                        ENGINE.start_or_resume_forge(force_routes_only=True)
                return _h

            def _make_deploy(j_str, m_mode):
                def _h(e):
                    ENGINE.deploy_jobs_to_sd_map([j_str], mode=m_mode)
                return _h

            def _make_prune(j_str):
                def _h(e):
                    if ENGINE.is_busy_transferring():
                        return
                    ENGINE.delete_or_prune_map(j_str, prune_high_res_only=True)
                    refresh_vault_column()
                    update_disk_audit_label()
                    page.update()
                return _h

            def _make_del(j_str):
                def _h(e):
                    if ENGINE.is_busy_transferring():
                        return
                    ENGINE.delete_or_prune_map(j_str, prune_high_res_only=False)
                    refresh_vault_column()
                    update_disk_audit_label()
                    page.update()
                return _h

            btns = []
            if rec_saved and (m["status"] != "COMPLETADO" or m["completed_tiles"] < m["total_tiles"] or m["size_mb"] < 0.1):
                btns.append(ft.ElevatedButton(ENGINE.tr("btn_item_resume"), disabled=busy_now, bgcolor=C_GREEN, color="#000000", on_click=_make_resume(rec_saved)))

            if rec_saved:
                btns.append(ft.ElevatedButton(ENGINE.tr("btn_item_add_routes"), disabled=busy_now, bgcolor=C_DARK, color=C_CYAN, on_click=_make_build_routes_only(rec_saved)))

            same_drive = (ENGINE.target_drive_root == ENGINE.sd_deploy_drive_root)

            btns.append(ft.ElevatedButton(ENGINE.tr("btn_item_merge_keep"), disabled=busy_now, bgcolor=C_CYAN, color="#000000", on_click=_make_deploy(jid, "MERGE_KEEP")))
            btns.append(ft.ElevatedButton(ENGINE.tr("btn_item_merge_move"), disabled=busy_now or same_drive, bgcolor=C_GREEN, color="#000000", on_click=_make_deploy(jid, "MERGE_MOVE")))
            btns.append(ft.ElevatedButton(ENGINE.tr("btn_item_direct_move"), disabled=busy_now or same_drive, bgcolor=C_AMBER, color="#000000", on_click=_make_deploy(jid, "DIRECT_MOVE")))
            if m["has_high_res"]:
                btns.append(ft.ElevatedButton(ENGINE.tr("btn_item_slim"), disabled=busy_now, bgcolor=C_DARK, color=C_AMBER, on_click=_make_prune(jid)))
            btns.append(ft.ElevatedButton(ENGINE.tr("btn_item_del"), disabled=busy_now, bgcolor=C_CRIT, color="#FFFFFF", on_click=_make_del(jid)))

            qoi_tag = f"Mapa: {m['zooms_summary']} ({m['qoi_count']} clústeres .QOI)" if m["qoi_count"] > 0 else "Mapa: Sin imágenes .QOI"
            hwy_tag = f"Rutas: ✔ ARTERIAL + {m['sec_count']:,} sectores .HWY" if m["has_hwy"] else "Rutas: ⚠ Sin rutas .HWY"

            col_vault_items.controls.append(
                ft.Container(
                    bgcolor=C_CARD,
                    padding=12,
                    border_radius=6,
                    border=ft.border.all(1, C_CYAN),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                wrap=True,
                                controls=[
                                    ft.Text(f"{m['job_name']}  [{m['status']}]", color="#FFFFFF", weight=ft.FontWeight.BOLD, size=14),
                                    ft.Text(f"{m['style_name']}  |  {qoi_tag}  |  {hwy_tag}  |  Peso: {m['size_mb']:,.1f} MB", color="#CCCCCC", size=12),
                                ]
                            ),
                            ft.Row(spacing=6, wrap=True, controls=btns)
                        ]
                    )
                )
            )

    view_phase_4 = ft.Container(
        visible=False,
        expand=True,
        bgcolor=C_PANEL,
        padding=20,
        border_radius=8,
        border=ft.border.all(1, C_CYAN),
        content=ft.Column(
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                txt_s4_title,
                txt_s4_sub,
                ft.Row(spacing=10, wrap=True, controls=[dd_sd_drive, btn_refresh_s4]),
                txt_disk_audit_s4,
                box_sd_merge_notice,
                box_legend_step4,
                ft.Container(
                    bgcolor=C_CARD,
                    padding=12,
                    border_radius=6,
                    border=ft.border.all(1, C_DARK),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            txt_mass_ops_title,
                            ft.Row(spacing=8, wrap=True, controls=[btn_global_merge_keep, btn_global_merge_move, btn_global_direct_move])
                        ]
                    )
                ),
                txt_single_ops_title,
                col_vault_items,
            ]
        )
    )

    wizard_stage_stack = ft.Column(
        expand=True,
        controls=[view_phase_0, view_phase_1, view_phase_2, view_phase_3, view_phase_4]
    )

    phase_boxes = []
    for step_idx in range(5):
        t_head = ft.Text("", size=13, weight=ft.FontWeight.BOLD)
        t_sub = ft.Text("", size=11)
        t_lock = ft.Text("", size=10, weight=ft.FontWeight.BOLD)

        def _make_phase_click(s_num):
            def _on_click(e):
                switch_wizard_phase(s_num)
            return _on_click

        box = ft.Container(
            expand=1,
            padding=10,
            border_radius=8,
            on_click=_make_phase_click(step_idx),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
                controls=[t_head, t_sub, t_lock]
            )
        )
        phase_boxes.append((step_idx, box, t_head, t_sub, t_lock))

    bottom_stepper_bar = ft.Container(
        bgcolor=C_PANEL,
        padding=10,
        border_radius=8,
        border=ft.border.all(1, C_DARK),
        content=ft.Row(spacing=10, controls=[b[1] for b in phase_boxes])
    )

    def apply_language_to_all_static_widgets():
        usb_str = info_ips["usb"][0] if info_ips["usb"] else ENGINE.tr("usb_wait")
        txt_s0_title.value = ENGINE.tr("step0_title")
        txt_s0_sub.value = ENGINE.tr("step0_sub")

        txt_s1_title.value = ENGINE.tr("step1_title")
        txt_s1_sub.value = ENGINE.tr("step1_sub")
        txt_cred_box_title.value = ENGINE.tr("cred_box_title")
        txt_ip_wifi_line.value = f"{ENGINE.tr('ip_wifi_lbl')}  {main_ip_val}     |     {ENGINE.tr('pin_lbl')}  {SERVER_PIN}"
        txt_ip_usb_line.value = f"{ENGINE.tr('ip_usb_lbl')}  {usb_str}"

        txt_opt_a_title.value = ENGINE.tr("opt_a_title")
        txt_opt_a_body.value = ENGINE.tr("opt_a_body")
        txt_opt_b_title.value = ENGINE.tr("opt_b_title")
        txt_opt_b_body.value = ENGINE.tr("opt_b_body")
        txt_opt_c_title.value = ENGINE.tr("opt_c_title")
        txt_opt_c_body.value = ENGINE.tr("opt_c_body")
        btn_pick_file.text = ENGINE.tr("btn_pick_file")
        btn_to_step2.text = ENGINE.tr("btn_to_step2")
        btn_to_step4_direct.text = ENGINE.tr("btn_to_step4_direct")

        txt_s2_title.value = ENGINE.tr("step2_title")
        dd_drives.label = ENGINE.tr("dd_pc_drive")
        btn_refresh_s2.text = ENGINE.tr("btn_refresh_drives")
        txt_s2_1_title.value = ENGINE.tr("step2_1_title")
        txt_fire_status.value = ENGINE.tr("step2_1_desc")
        btn_fire_test.text = ENGINE.tr("btn_fire_test")
        btn_back_s1.text = ENGINE.tr("btn_back_step1")
        btn_to_s3.text = ENGINE.tr("btn_to_step3")

        txt_s3_title.value = ENGINE.tr("step3_title")
        btn_go_phase4_from_3.text = ENGINE.tr("btn_go_step4")
        lbl_clock_active.value = ENGINE.tr("clock_active")
        lbl_clock_eta.value = ENGINE.tr("clock_eta")
        lbl_clock_speed.value = ENGINE.tr("clock_speed")
        btn_start_s3.text = ENGINE.tr("btn_start")
        btn_pause_s3.text = ENGINE.tr("btn_pause")
        btn_stop_s3.text = ENGINE.tr("btn_stop")

        dd_threads.label = ENGINE.tr("dd_threads")
        dd_threads.options = [
            ft.dropdown.Option(str(safe_t), ENGINE.tr("th_std")),
            ft.dropdown.Option(str(fast_t), ENGINE.tr("th_fast")),
            ft.dropdown.Option(str(turbo_t), ENGINE.tr("th_max")),
        ]
        dd_rate.label = ENGINE.tr("dd_speed")
        dd_rate.options = [
            ft.dropdown.Option("80", ENGINE.tr("spd_slow")),
            ft.dropdown.Option("140", ENGINE.tr("spd_norm")),
            ft.dropdown.Option("180", ENGINE.tr("spd_fast")),
            ft.dropdown.Option("220", ENGINE.tr("spd_turbo")),
        ]
        lbl_live_strip.value = ENGINE.tr("live_strip_lbl")
        lbl_witness_strip.value = ENGINE.tr("witness_strip_lbl")

        txt_s4_title.value = ENGINE.tr("step4_title")
        txt_s4_sub.value = ENGINE.tr("step4_sub")
        dd_sd_drive.label = ENGINE.tr("dd_sd_drive")
        btn_refresh_s4.text = ENGINE.tr("btn_refresh_drives")
        txt_mass_ops_title.value = ENGINE.tr("mass_ops_title")
        btn_global_merge_keep.text = ENGINE.tr("btn_all_merge_keep")
        btn_global_merge_move.text = ENGINE.tr("btn_all_merge_move")
        btn_global_direct_move.text = ENGINE.tr("btn_all_direct_move")
        txt_single_ops_title.value = ENGINE.tr("single_ops_title")

    def update_stepper_visuals_and_locks():
        busy = ENGINE.is_busy_transferring()
        dd_drives.disabled = busy
        dd_sd_drive.disabled = busy
        dd_style_override.disabled = busy

        same_drive = (ENGINE.target_drive_root == ENGINE.sd_deploy_drive_root)

        btn_global_merge_keep.disabled = busy
        btn_global_merge_move.disabled = busy or same_drive
        btn_global_direct_move.disabled = busy or same_drive

        if same_drive and ENGINE.wizard_step == 4:
            txt_disk_audit_s4.value = "⚠ EL DISCO DE LA PC Y EL DESTINO SON EL MISMO. CONECTA TU MICRO-SD Y PULSA 'ACTUALIZAR DISCOS', O USA 'COMBINAR (DEJAR EN PC)'."
            txt_disk_audit_s4.color = C_AMBER

        view_phase_0.visible = (ENGINE.wizard_step == 0)
        view_phase_1.visible = (ENGINE.wizard_step == 1)
        view_phase_2.visible = (ENGINE.wizard_step == 2)
        view_phase_3.visible = (ENGINE.wizard_step == 3)
        view_phase_4.visible = (ENGINE.wizard_step == 4)

        btn_go_phase4_from_3.visible = (ENGINE.state == "COMPLETED")

        nav_keys = ["nav_s0", "nav_s1", "nav_s2", "nav_s3", "nav_s4"]
        for (p_num, box, t_head, t_sub, t_lock) in phase_boxes:
            h_txt, s_txt = ENGINE.tr(nav_keys[p_num])
            t_head.value = h_txt
            t_sub.value = s_txt

            if p_num == ENGINE.wizard_step:
                box.bgcolor = "#062618"
                box.border = ft.border.all(2, C_GREEN)
                t_head.color = C_GREEN
                t_sub.color = "#FFFFFF"
                t_lock.value = ENGINE.tr("st_current")
                t_lock.color = C_GREEN
            else:
                allowed, _ = can_navigate_to_phase(p_num)
                if allowed:
                    box.bgcolor = C_CARD
                    box.border = ft.border.all(1, C_CYAN)
                    t_head.color = C_CYAN
                    t_sub.color = "#CCCCCC"
                    t_lock.value = ENGINE.tr("st_avail")
                    t_lock.color = C_CYAN
                else:
                    box.bgcolor = C_LOCKED_BG
                    box.border = ft.border.all(1, C_LOCKED_BORDER)
                    t_head.color = C_LOCKED_TEXT
                    t_sub.color = C_LOCKED_TEXT
                    t_lock.value = ENGINE.tr("st_locked") if busy else ENGINE.tr("st_pending")
                    t_lock.color = C_LOCKED_TEXT

    last_seq = [0]
    ui_render_lock = threading.Lock()

    def sync_ui_from_engine(refresh_vault: bool = True):
        # Si otro hilo ya está dentro de page.update(), salir de inmediato sin bloquear ni colisionar en Flet
        if not ui_render_lock.acquire(blocking=False):
            return
        try:
            ENGINE.update_telemetry_strings()
            rec = ENGINE.active_recipe
            is_routes_only = getattr(ENGINE, "running_routes_only_pass", False) or (rec.get("routes_only", False) if rec else False)

            # 1. Actualizar barra de Rutas (.HWY) con porcentaje explícito
            r_prog = min(1.0, max(0.0, getattr(ENGINE, "routes_progress", 0.0)))
            pb_routes.value = r_prog
            txt_pb_routes_pct.value = f"{r_prog * 100:.1f}%"
            lbl_pb_routes.value = getattr(ENGINE, "routes_status_str", "") or "1. RED VIAL Y CALLES (.HWY): En espera..."

            # 2. Actualizar barra de Teselas (.QOI) con conteo y porcentaje explícito
            if is_routes_only:
                pb_main.value = 0.0
                txt_pb_tiles_pct.value = "OMITIDO"
                lbl_pb_tiles.value = "2. IMÁGENES DEL MAPA (.QOI): No solicitadas (Este pedido es únicamente de Rutas .HWY)"
            elif ENGINE.total_sectors > 0:
                t_prog = min(1.0, ENGINE.completed_sectors / float(ENGINE.total_sectors))
                pb_main.value = t_prog
                txt_pb_tiles_pct.value = f"{t_prog * 100:.1f}%"
                zooms_list = sorted(rec.get("selected_zooms", [])) if rec else []
                txt_zooms = f"Z{zooms_list[0]}-Z{zooms_list[-1]}" if zooms_list else "Z?"
                lbl_pb_tiles.value = (
                    f"2. IMÁGENES DEL MAPA ({txt_zooms}): "
                    f"{ENGINE.completed_sectors:,} / {ENGINE.total_sectors:,} cuadros .QOI guardados"
                )
            else:
                pb_main.value = 0.0
                txt_pb_tiles_pct.value = "0.0%"
                lbl_pb_tiles.value = "2. IMÁGENES DEL MAPA (.QOI): Calculando sectores..."

            txt_clock_elapsed.value = ENGINE.elapsed_formatted
            if ENGINE.state == "PREPARING":
                txt_clock_eta.value = f"~{ENGINE._format_mm_ss(ENGINE.prep_countdown_seconds)}"
                txt_clock_eta.color = C_AMBER
                txt_clock_speed.value = "..."
            else:
                txt_clock_eta.value = ENGINE.eta_formatted
                txt_clock_eta.color = C_GREEN
                if is_routes_only or ENGINE.state == "WAITING_ROUTES":
                    kbps_now = getattr(ENGINE, "routes_kbps", 0.0)
                    txt_clock_speed.value = f"{kbps_now:.0f} KB/s" if kbps_now > 0.5 else "RUTAS .HWY"
                else:
                    txt_clock_speed.value = f"{ENGINE.current_tps:.1f} /s"

            jname_cur = rec.get("job_name", "") if rec else ""
            if ENGINE.state == "PAUSED_USER":
                txt_giant_state_title.value = ENGINE.tr("banner_paused_title")
                txt_giant_state_title.color = C_AMBER
                txt_giant_state_sub.value = ENGINE.tr("banner_paused_sub")
                giant_status_banner.bgcolor = "#1F1400"
                giant_status_banner.border = ft.border.all(3, C_AMBER)
            elif ENGINE.state == "PAUSED_NET":
                txt_giant_state_title.value = ENGINE.tr("banner_net_title")
                txt_giant_state_title.color = C_CRIT
                txt_giant_state_sub.value = ENGINE.tr("banner_net_sub")
                giant_status_banner.bgcolor = "#22050A"
                giant_status_banner.border = ft.border.all(3, C_CRIT)
            elif ENGINE.state == "PREPARING":
                cd_str = ENGINE._format_mm_ss(ENGINE.prep_countdown_seconds)
                txt_giant_state_title.value = ENGINE.tr("banner_prep_title").format(cd=cd_str)
                txt_giant_state_title.color = C_AMBER
                txt_giant_state_sub.value = ENGINE.tr("banner_prep_sub")
                giant_status_banner.bgcolor = "#161204"
                giant_status_banner.border = ft.border.all(2, C_AMBER)
            elif ENGINE.state == "WAITING_ROUTES":
                txt_giant_state_title.value = f"⏳ TERMINANDO DE COMPILAR RUTAS ({r_prog * 100:.1f}%)"
                txt_giant_state_title.color = C_CYAN
                txt_giant_state_sub.value = ENGINE.routes_status_str
                giant_status_banner.bgcolor = "#001A1F"
                giant_status_banner.border = ft.border.all(2, C_CYAN)
            elif ENGINE.state in ("RUNNING", "FLUSHING_DISK"):
                if is_routes_only:
                    pct_now = r_prog * 100.0
                    txt_giant_state_title.value = f"⚡ COMPILANDO RUTAS: {jname_cur} ({pct_now:.1f}%)"
                    txt_giant_state_sub.value = ENGINE.routes_status_str
                else:
                    pct_now = (ENGINE.completed_sectors * 100.0 / max(1, ENGINE.total_sectors))
                    txt_giant_state_title.value = ENGINE.tr("banner_run_title").format(name=jname_cur, pct=pct_now)
                    txt_giant_state_sub.value = ENGINE.tr("banner_run_sub").format(eta=ENGINE.eta_formatted)
                txt_giant_state_title.color = C_GREEN
                giant_status_banner.bgcolor = "#041A0E"
                giant_status_banner.border = ft.border.all(2, C_GREEN)
            elif ENGINE.state == "COMPLETED":
                txt_giant_state_title.value = ENGINE.tr("banner_done_title")
                txt_giant_state_title.color = C_GREEN
                txt_giant_state_sub.value = ENGINE.tr("banner_done_sub")
                giant_status_banner.bgcolor = "#041A0E"
                giant_status_banner.border = ft.border.all(2, C_GREEN)
            else:
                txt_giant_state_title.value = ENGINE.tr("banner_ready_title")
                txt_giant_state_title.color = C_GREEN
                txt_giant_state_sub.value = ENGINE.tr("banner_ready_sub")
                giant_status_banner.bgcolor = C_CARD
                giant_status_banner.border = ft.border.all(2, C_GREEN)

            pb_sd_merge.value = min(1.0, max(0.0, ENGINE.sd_merge_progress))
            if ENGINE.state == "MERGING_SD":
                txt_sd_merge_notice.value = ENGINE.tr("transferring_msg").format(pct=ENGINE.sd_merge_progress * 100.0)
                txt_sd_merge_notice.color = C_AMBER
                pb_sd_merge.color = C_AMBER
                box_sd_merge_notice.border = ft.border.all(1, C_AMBER)
            elif ENGINE.sd_transfer_done:
                txt_sd_merge_notice.value = ENGINE.tr("transfer_done_msg")
                txt_sd_merge_notice.color = C_GREEN
                pb_sd_merge.color = C_GREEN
                box_sd_merge_notice.border = ft.border.all(2, C_GREEN)
            else:
                txt_sd_merge_notice.value = ENGINE.tr("step4_ready_msg")
                txt_sd_merge_notice.color = C_CYAN
                pb_sd_merge.color = C_CYAN
                box_sd_merge_notice.border = ft.border.all(1, C_CYAN)

            if rec:
                msg_ord = ENGINE.tr("order_ready").format(
                    name=rec.get("job_name", "Mapa"),
                    mode_str="SOLO RUTAS (.HWY)" if is_routes_only else "MAPA (.QOI) + RUTAS",
                    mb=rec.get("estimated_weight_mb", 0.0)
                )
                txt_recipe_summary_s1.value = msg_ord
                txt_recipe_summary_s1.color = C_GREEN
                txt_recipe_summary_s2.value = msg_ord
                update_disk_audit_label()
            else:
                txt_recipe_summary_s1.value = ENGINE.tr("waiting_order")
                txt_recipe_summary_s1.color = C_AMBER
                txt_recipe_summary_s2.value = ENGINE.tr("waiting_order")
                update_disk_audit_label()

            if ENGINE.sample_seq != last_seq[0]:
                with ENGINE._lock:
                    last_seq[0] = ENGINE.sample_seq
                    row_live_samples_list = list(ENGINE.live_samples)[::-1]
                    row_witness_list = list(ENGINE.witness_samples)[::-1]

                row_live_strip.controls.clear()
                for s in row_live_samples_list:
                    row_live_strip.controls.append(
                        ft.Container(
                            bgcolor=C_DARK, padding=4, border_radius=6,
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2,
                                controls=[
                                    ft.Image(src_base64=s["b64"], width=64, height=64),
                                    ft.Text(f"Z{s['z']} ({s['kb']:.1f}K)", size=9, color=C_GREEN)
                                ]
                            )
                        )
                    )

                row_witness_strip.controls.clear()
                for ws in row_witness_list:
                    row_witness_strip.controls.append(
                        ft.Container(
                            bgcolor=C_DARK, padding=4, border_radius=6,
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2,
                                controls=[
                                    ft.Image(src_base64=ws["b64"], width=64, height=64),
                                    ft.Text(f"Z{ws['z']}", size=9, color=C_CYAN)
                                ]
                            )
                        )
                    )

            if refresh_vault:
                refresh_vault_column()
            update_stepper_visuals_and_locks()
            page.update()
        except Exception:
            pass
        finally:
            ui_render_lock.release()

    ENGINE.on_ui_refresh = lambda: sync_ui_from_engine(refresh_vault=(ENGINE.wizard_step == 4))

    def _ui_ticker():
        while True:
            time.sleep(0.45)
            if ENGINE.is_busy_transferring():
                sync_ui_from_engine(refresh_vault=False)

    threading.Thread(target=_ui_ticker, daemon=True).start()

    apply_language_to_all_static_widgets()
    sync_ui_from_engine(refresh_vault=False)
    page.add(wizard_stage_stack, bottom_stepper_bar)


if __name__ == "__main__":
    start_http_server()
    ft.app(target=main)