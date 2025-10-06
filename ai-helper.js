// AI Helper - инжектируется на любую страницу
(async function() {
  'use strict';

  const API_KEY = 'AIzaSyDmJEzLEv3Qo50iFoYJ5jWCda49m3jCK5I';
  
  // Проверка: если уже запущено - удаляем
  if (document.getElementById('ai-helper-overlay')) {
    document.getElementById('ai-helper-overlay').remove();
    return;
  }

  // Создаём overlay для результата
  const overlay = document.createElement('div');
  overlay.id = 'ai-helper-overlay';
  overlay.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    padding: 25px 40px;
    border-radius: 15px;
    font-size: 28px;
    font-weight: bold;
    z-index: 2147483647;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    font-family: Arial, sans-serif;
    text-align: center;
    min-width: 200px;
    animation: slideInFromRight 0.4s ease-out;
  `;

  // Добавляем анимацию
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideInFromRight {
      from {
        transform: translateX(500px);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }
    @keyframes slideOutToRight {
      to {
        transform: translateX(500px);
        opacity: 0;
      }
    }
    @keyframes pulse {
      0%, 100% { transform: scale(1); }
      50% { transform: scale(1.05); }
    }
  `;
  document.head.appendChild(style);

  overlay.innerHTML = `
    <div style="font-size:16px;opacity:0.9;margin-bottom:5px">🤖 AI думает...</div>
    <div style="font-size:42px;animation:pulse 1.5s ease-in-out infinite">⏳</div>
  `;
  document.body.appendChild(overlay);

  try {
    // Делаем скриншот текущей страницы
    const canvas = document.createElement('canvas');
    const width = Math.min(window.innerWidth, 1920);
    const height = Math.min(window.innerHeight, 1080);
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');

    // Фон
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, width, height);

    // Пробуем захватить изображения (если есть)
    const images = document.querySelectorAll('img');
    for (let img of images) {
      if (img.complete && img.naturalHeight !== 0) {
        try {
          const rect = img.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            ctx.drawImage(img, rect.left, rect.top, rect.width, rect.height);
          }
        } catch(e) {
          console.log('Не удалось загрузить картинку:', e);
        }
      }
    }

    const screenshot = canvas.toDataURL('image/jpeg', 0.6).split(',')[1];
    
    // Получаем текст страницы
    const pageText = document.body.innerText.substring(0, 10000);

    overlay.innerHTML = `
      <div style="font-size:16px;opacity:0.9;margin-bottom:5px">🧠 Анализирую...</div>
      <div style="font-size:42px;animation:pulse 1.5s ease-in-out infinite">🤔</div>
    `;

    // Отправляем в Gemini AI
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=${API_KEY}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{
            parts: [
              {
                text: `Это страница теста/экзамена. Найди правильный ответ.

ВАЖНО: Верни ТОЛЬКО ОДНУ БУКВУ (A, B, C, D, E или А, Б, В, Г, Д).
Никаких объяснений, точек, скобок - ТОЛЬКО БУКВА!

Если это True/False - верни T или F.
Если несколько вопросов - отвечай на первый.

Текст страницы:
${pageText}`
              },
              {
                inline_data: {
                  mime_type: 'image/jpeg',
                  data: screenshot
                }
              }
            ]
          }],
          generationConfig: {
            temperature: 0.1,
            maxOutputTokens: 5
          }
        })
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    console.log('AI Response:', data);

    if (!data.candidates || !data.candidates[0]) {
      throw new Error('AI не вернул ответ');
    }

    const aiText = data.candidates[0].content.parts[0].text.trim();
    console.log('AI text:', aiText);

    // Извлекаем букву
    let answer = '?';
    const match = aiText.match(/[A-EАБВГДTF]/i);
    if (match) {
      answer = match[0].toUpperCase();
    } else if (aiText.length <= 3) {
      answer = aiText.toUpperCase();
    }

    // Показываем результат
    overlay.innerHTML = `
      <div style="font-size:18px;opacity:0.95;margin-bottom:8px">✅ Ответ:</div>
      <div style="font-size:72px;letter-spacing:8px;text-shadow:0 4px 8px rgba(0,0,0,0.3);animation:pulse 2s ease-in-out infinite">${answer}</div>
      <div style="font-size:12px;opacity:0.8;margin-top:10px;cursor:pointer" onclick="this.parentElement.remove()">
        (кликни чтобы закрыть)
      </div>
    `;

    // Автоудаление через 15 секунд
    setTimeout(() => {
      overlay.style.animation = 'slideOutToRight 0.4s ease-in';
      setTimeout(() => overlay.remove(), 400);
    }, 15000);

  } catch (error) {
    console.error('AI Helper Error:', error);
    overlay.innerHTML = `
      <div style="font-size:18px;margin-bottom:8px">❌ Ошибка</div>
      <div style="font-size:14px;opacity:0.9">${error.message}</div>
      <div style="font-size:12px;margin-top:10px;cursor:pointer" onclick="this.parentElement.remove()">
        (кликни чтобы закрыть)
      </div>
    `;
    
    setTimeout(() => overlay.remove(), 8000);
  }
})();
