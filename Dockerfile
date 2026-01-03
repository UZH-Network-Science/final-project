# Read the doc: https://huggingface.co/docs/hub/spaces-sdks-docker
# Usage:
# docker build -t network-analysis .
# docker run -it -p 7860:7860 network-analysis

FROM python:3.14-slim

# Create a non-root user
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Copy requirements first for cache efficiency
COPY --chown=user ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# Running networkx patch
COPY --chown=user ./scripts/patch_networkx.py /app/scripts/patch_networkx.py
RUN python3 scripts/patch_networkx.py

# Copy required files
COPY --chown=user ./src /app/src
COPY --chown=user ./docs/analysis/Comparison_Analysis.ipynb /app/docs/analysis/Comparison_Analysis.ipynb
COPY --chown=user ./metrics /app/metrics
COPY --chown=user ./datasets/japan/japan_rail_network.gpickle /app/datasets/japan/japan_rail_network.gpickle
COPY --chown=user ./datasets/switzerland/swiss_rail_network_unified.gpickle /app/datasets/switzerland/swiss_rail_network_unified.gpickle
COPY --chown=user ./voila.json /app/voila.json

# Trust the notebook to allow Javascript execution
RUN jupyter trust docs/analysis/Comparison_Analysis.ipynb

# Expose Hugging Face's default port
EXPOSE 7860

# See voila.json for VoilaConfiguration, VoilaExecutor, MappingKernelManager settings
CMD ["voila", "docs/analysis/Comparison_Analysis.ipynb", "--port=7860", "--no-browser", "--Voila.ip=0.0.0.0"]

