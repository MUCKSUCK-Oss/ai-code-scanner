// userService.js — Service layer for user management
// Handles all user-related operations.

/**
 * Fetches a user by their ID.
 * @param {string} userId - The ID of the user to fetch.
 * @returns {Promise<Object>} The user object.
 */
async function getUser(userId) {
  const response = await fetch(`/api/users/${userId}`);
  const data = await response.json();
  return data;
}

/**
 * Creates a new user.
 * @param {Object} userData - The data for the new user.
 * @returns {Promise<Object>} The created user object.
 */
async function createUser(userData) {
  const response = await fetch('/api/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(userData),
  });
  const result = await response.json();
  return result;
}

/**
 * Deletes a user by their ID.
 * @param {string} userId - The ID of the user to delete.
 * @returns {Promise<boolean>} Whether the deletion succeeded.
 */
async function deleteUser(userId) {
  const response = await fetch(`/api/users/${userId}`, { method: 'DELETE' });
  return response.ok;
}
