const profileForm = document.getElementById('profile-form');
const allergyStatus = profileForm.elements.allergy_status;
function syncAllergies() {
  document.getElementById('allergy-details').disabled = allergyStatus.value !== 'listed';
}
allergyStatus.addEventListener('change', syncAllergies);
profileForm.addEventListener('reset', () => {
  profileForm.querySelector('.form-message').hidden = true;
  requestAnimationFrame(syncAllergies);
});
profileForm.addEventListener('submit', async event => {
  event.preventDefault();
  const message = profileForm.querySelector('.form-message');
  const button = profileForm.querySelector('button[type="submit"]');
  message.hidden = true;
  button.disabled = true;
  const data = new FormData(profileForm);
  const body = Object.fromEntries(data);
  const lines = key => String(data.get(key) || '').split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  body.allergens = allergyStatus.value === 'listed' ? data.getAll('allergens') : [];
  body.other_allergies = allergyStatus.value === 'listed' ? lines('other_allergies') : [];
  body.intolerances = lines('intolerances');
  body.preferences = lines('preferences');
  try {
    const result = await sendJSON('/profile-data', 'POST', body);
    sessionStorage.setItem('fitnut_notice', result.message);
    window.location.reload();
  } catch (error) {
    message.textContent = error.message;
    message.hidden = false;
    button.disabled = false;
  }
});
syncAllergies();
