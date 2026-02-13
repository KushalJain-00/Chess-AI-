# Contributing to Chess AI

First off, thank you for considering contributing to Chess AI! 🎉

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating bug reports, please check existing issues. When you create a bug report, include as many details as possible:

**Bug Report Template:**
```
**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. See error

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**
 - OS: [e.g. Windows 10, macOS 12.0]
 - Python Version: [e.g. 3.9.7]
 - Pygame Version: [e.g. 2.5.0]

**Additional context**
Any other context about the problem.
```

### 💡 Suggesting Features

Feature suggestions are welcome! Please provide:
- Clear description of the feature
- Why it would be useful
- Possible implementation approach

### 🔧 Pull Requests

1. **Fork the repo** and create your branch from `main`
2. **Make your changes**
   - Follow the code style (PEP 8)
   - Add comments for complex logic
   - Update documentation if needed
3. **Test your changes** thoroughly
4. **Commit with clear messages**
   ```bash
   git commit -m "Add feature: XYZ"
   git commit -m "Fix bug: ABC"
   ```
5. **Push to your fork** and submit a PR

### 📝 Code Style Guidelines

- Follow **PEP 8** style guide
- Use **meaningful variable names**
- Add **docstrings** for functions
- **Comment complex logic**
- Keep functions **focused and small**

**Example:**
```python
def evaluate_king_safety(color):
    """
    Evaluate king safety based on pawn shield and piece proximity.
    
    Args:
        color (str): 'white' or 'black'
    
    Returns:
        int: Safety score (positive = safe, negative = exposed)
    """
    # Implementation here
    pass
```

### 🧪 Testing

- Test your changes in different scenarios
- Try all difficulty levels
- Check edge cases (stalemate, promotion, etc.)

### 📋 PR Checklist

Before submitting, ensure:
- [ ] Code follows style guidelines
- [ ] Comments added for complex parts
- [ ] README updated if feature visible to users
- [ ] No new warnings or errors
- [ ] Tested thoroughly

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/Chess-AI-.git
cd Chess-AI-

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create a branch
git checkout -b feature/my-awesome-feature

# Make changes and test
python chess_v2.py

# Commit and push
git add .
git commit -m "Description of changes"
git push origin feature/my-awesome-feature
```

## Areas That Need Help

### 🔥 High Priority
- [ ] Opening book implementation
- [ ] Endgame tablebase integration
- [ ] Performance profiling and optimization
- [ ] Unit tests for game logic

### 🎯 Medium Priority
- [ ] Additional board themes
- [ ] Custom piece sets
- [ ] PGN import/export
- [ ] Better documentation

### 💡 Ideas Welcome
- Neural network evaluation
- Online multiplayer
- Mobile version
- Puzzle mode

## Questions?

Feel free to:
- Open an issue for questions
- Start a discussion
- Reach out to [@KushalJain-00](https://github.com/KushalJain-00)

## Code of Conduct

### Our Pledge

We are committed to making participation in this project a harassment-free experience for everyone.

### Our Standards

**Positive behavior:**
- Being respectful
- Being welcoming
- Accepting constructive criticism
- Focusing on what's best for the project

**Unacceptable behavior:**
- Harassment or trolling
- Personal attacks
- Inappropriate content

## Recognition

Contributors will be recognized in:
- README.md (Contributors section)
- Release notes
- Special mentions for significant contributions

## Thank You! 🙏

Your contributions make this project better for everyone!

---

**Happy Coding!** ♟️
