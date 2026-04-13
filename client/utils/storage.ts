export const storage = {
  get: (key: string): string | null => localStorage.getItem(key),

  set: (key: string, value: string | null): void => {
    if (value) {
      localStorage.setItem(key, value);
    } else {
      localStorage.removeItem(key);
    }
  }
};