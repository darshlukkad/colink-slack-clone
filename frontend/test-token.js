// Quick test to check localStorage tokens
const tokens = localStorage.getItem('colink_tokens');
console.log('Stored tokens:', tokens);
if (tokens) {
  const parsed = JSON.parse(tokens);
  console.log('Access token:', parsed.access_token?.substring(0, 50) + '...');
  console.log('Refresh token:', parsed.refresh_token?.substring(0, 50) + '...');
}
