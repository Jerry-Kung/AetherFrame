/**
 * 复制文本到剪贴板，兼容非安全上下文（HTTP + 局域网 IP 访问）。
 *
 * navigator.clipboard 仅在安全上下文（HTTPS / localhost）下存在，
 * Docker 部署经 http://<ip>:8000 访问时为 undefined，
 * 此时回退到隐藏 textarea + document.execCommand("copy")。
 */
export async function copyTextToClipboard(text: string): Promise<boolean> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 权限被拒或文档失焦等，继续尝试降级方案
    }
  }
  return execCommandCopy(text);
}

function execCommandCopy(text: string): boolean {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  // 避免页面滚动和闪烁
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "-9999px";
  textarea.setAttribute("readonly", "");
  document.body.appendChild(textarea);
  const selection = document.getSelection();
  const prevRange = selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
  textarea.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  document.body.removeChild(textarea);
  if (prevRange && selection) {
    selection.removeAllRanges();
    selection.addRange(prevRange);
  }
  return ok;
}
