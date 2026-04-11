import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginPage } from '../pages/LoginPage';
import { useAuth } from '../hooks/useAuth';

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

describe('LoginPage', () => {
  const mockLogin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({
      login: mockLogin,
    });
  });

  it('test_renders_form', () => {
    render(<LoginPage />);
    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Login/i })).toBeInTheDocument();
  });

  it('test_submit_calls_login', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    
    await user.type(screen.getByLabelText(/Email/i), 'test@test.com');
    await user.type(screen.getByLabelText(/Password/i), '123456');
    await user.click(screen.getByRole('button', { name: /Login/i }));

    expect(mockLogin).toHaveBeenCalledWith('test@test.com', '123456');
  });

  it('test_error_displayed_on_failure', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'));
    const user = userEvent.setup();
    render(<LoginPage />);
    
    await user.type(screen.getByLabelText(/Email/i), 'test@test.com');
    await user.type(screen.getByLabelText(/Password/i), 'wrong');
    await user.click(screen.getByRole('button', { name: /Login/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Invalid credentials');
  });

  it('test_redirects_on_success', async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<LoginPage onSuccess={onSuccess} />);
    
    await user.type(screen.getByLabelText(/Email/i), 'test@test.com');
    await user.type(screen.getByLabelText(/Password/i), '123456');
    await user.click(screen.getByRole('button', { name: /Login/i }));

    expect(onSuccess).toHaveBeenCalled();
  });

  it('test_link_to_register', () => {
    render(<LoginPage />);
    const link = screen.getByRole('link', { name: /Register here/i });
    expect(link).toHaveAttribute('href', '/register');
  });
});
