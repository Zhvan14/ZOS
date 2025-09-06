read -p "Enter the name of the Python file (e.g., my_script.py): " py_file

if [ ! -f "$py_file" ]; then
    echo "Error: File '$py_file' not found."
    exit 1
fi

archive_xz="${py_file%.*}.tar.xz"
archive_zpkg="${py_file%.*}.zpkg"

echo "Compressing '$py_file' to '$archive_xz'..."
tar -cJf "$archive_xz" "$py_file"

if [ $? -eq 0 ]; then
    echo "Renaming '$archive_xz' to '$archive_zpkg'..."
    mv "$archive_xz" "$archive_zpkg"
    echo "Successfully created '$archive_zpkg'."
else
    echo "Error: 'tar' command failed. Aborting."
fi

exit 0

