let accessToken = '';

/** Keep the demo access code in memory only; never include provider credentials. */
export async function protectedFetch(url, options = {}) {
  const send = () => {
    const headers = new Headers(options.headers);
    if (accessToken) headers.set('Authorization', 'Bearer ' + accessToken);
    return fetch(url, { ...options, headers });
  };
  let response = await send();
  if (response.status === 401) {
    accessToken = '';
    const entered = window.prompt('이 기능의 접근 코드를 입력해주세요.');
    if (!entered) return response;
    accessToken = entered.trim();
    response = await send();
    if (response.status === 401) accessToken = '';
  }
  return response;
}

