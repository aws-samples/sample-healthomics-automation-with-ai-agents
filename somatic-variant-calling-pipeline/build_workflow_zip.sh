#!/bin/bash

filename="mutect.zip"

if [ -f "$filename" ]; then
  rm "$filename"
  echo "File '$filename' deleted."
else
  echo "File '$filename' does not exist."
fi

echo "Preparing zip"
zip $filename main.wdl
echo "Done"
