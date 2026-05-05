# Contributing to GlassNote AI

Thank you for your interest in contributing to GlassNote! We welcome contributions from the community.

## 🤝 How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- **Clear title**: Summarize the problem in one sentence
- **Steps to reproduce**: Detailed steps to reproduce the issue
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Environment**: OS, Python version, relevant config
- **Logs**: Any relevant error messages or logs

### Suggesting Features

We love new ideas! Open an issue with:
- **Use case**: Describe the problem you're trying to solve
- **Proposed solution**: How you envision the feature working
- **Alternatives**: Other approaches you've considered
- **Additional context**: Screenshots, mockups, or examples

### Submitting Pull Requests

1. **Fork the repository**
   ```bash
   git clone https://github.com/sshivasai/GlassNoteAI.git
   cd GlassNoteAI
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add tests for new features
   - Update documentation as needed

4. **Test your changes**
   ```bash
   # Backend
   cd backend
   pytest

   # GUI Client
   cd GUI
   python -m pytest

   # Website
   cd website
   npm run build
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add amazing new feature"
   ```

   Use conventional commit messages:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `style:` for formatting changes
   - `refactor:` for code refactoring
   - `test:` for adding tests
   - `chore:` for maintenance tasks

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**
   - Provide a clear description of the changes
   - Reference any related issues
   - Include screenshots for UI changes

## 📋 Development Guidelines

### Code Style

**Python (Backend & GUI)**
- Follow PEP 8
- Use type hints where appropriate
- Add docstrings for functions and classes
- Keep functions small and focused

**TypeScript/JavaScript (Website)**
- Use TypeScript for type safety
- Follow the existing component structure
- Use functional components with hooks
- Keep components small and reusable

### Testing

- Write tests for new features
- Maintain or improve code coverage
- Test edge cases and error handling

### Documentation

- Update README.md for user-facing changes
- Update SETUP.md for installation changes
- Add inline comments for complex logic
- Update API documentation for backend changes

## 🌟 Areas for Contribution

We especially welcome contributions in these areas:

### High Priority
- **macOS support**: Port GUI client to macOS
- **Linux support**: Port GUI client to Linux
- **Performance optimization**: Reduce latency, memory usage
- **Test coverage**: Add more unit and integration tests
- **Documentation**: Improve setup guides, add video tutorials

### Feature Ideas
- **Multi-language support**: Support for non-English meetings
- **Custom prompts**: Allow users to customize AI prompts
- **Session replay**: Review past sessions with AI responses
- **Browser extension**: Chrome/Edge extension for web meetings
- **Mobile companion**: iOS/Android app for session control

### Bug Fixes
- Check our [Issues](https://github.com/sshivasai/GlassNoteAI/issues) page for open bugs

## 🔍 Review Process

1. **Initial Review**: Maintainers will review within 48 hours
2. **Feedback**: We may request changes or clarifications
3. **Testing**: All tests must pass before merging
4. **Approval**: Two maintainer approvals required
5. **Merge**: We'll merge and include in the next release

## 📜 Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## 🙋 Getting Help

- **Questions**: Open a [Discussion](https://github.com/sshivasai/GlassNoteAI/discussions)
- **Bugs**: Open an [Issue](https://github.com/sshivasai/GlassNoteAI/issues)
- **Email**: [support@glassnote.ai](mailto:support@glassnote.ai)

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to GlassNote! 🎉
