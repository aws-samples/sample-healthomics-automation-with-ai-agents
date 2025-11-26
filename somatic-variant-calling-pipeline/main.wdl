version 1.1

## Mutect2 Workflow with Cooking Show Mode
## When cooking_show_mode=true, tasks log inputs and create placeholder outputs

struct Runtime {
    String gatk_docker
    Int cpu
    Int machine_mem
    Int command_mem
}

workflow Mutect2 {
    input {
        # basic inputs
        File? intervals
        File ref_fasta
        File ref_fai
        File ref_dict
        File tumor_reads
        File tumor_reads_index
        File normal_reads
        File normal_reads_index
        String normal_sample_name
        String tumor_sample_name

        # optional resources
        File? pon
        File? pon_idx
        File? gnomad
        File? gnomad_idx
        File? variants_for_contamination
        File? variants_for_contamination_idx

        # extra arguments
        String? m2_extra_args
        String? m2_extra_filtering_args
        String? getpileupsummaries_extra_args
        String? split_intervals_extra_args

        # additional modes
        Boolean run_orientation_bias_mixture_model_filter = false
        Boolean make_bamout = false
        Boolean compress_vcfs = false

        # runtime
        String gatk_docker="quay.io/biocontainers/gatk4:4.6.2.0--py310hdfd78af_1"
        Int scatter_count
        Int small_task_cpu
        Int small_task_mem

        # cooking show mode - when true, tasks will only log inputs and create placeholder outputs
        Boolean cooking_show_mode = false
        Boolean vcf2maf = true
        String aws_region = "us-east-1"
        # vcf2maf output file based on AWS region
        File vcf2maf_output = "s3://aws-genomics-static-~{aws_region}/omics-data/tumor-normal/maf/test_civic.maf"
    }

    Runtime standard_runtime = Runtime {"gatk_docker": gatk_docker,
                                        "cpu": small_task_cpu,
                                        "machine_mem": small_task_mem * 1024,
                                        "command_mem": (small_task_mem * 1024) - 512}

    call SplitIntervals {
        input:
            intervals = intervals,
            ref_fasta = ref_fasta,
            ref_fai = ref_fai,
            ref_dict = ref_dict,
            scatter_count = scatter_count,
            split_intervals_extra_args = split_intervals_extra_args,
            runtime_params = standard_runtime,
            cooking_show_mode = cooking_show_mode
    }

    scatter (subintervals in SplitIntervals.interval_files) {
        call M2 {
            input:
                intervals = subintervals,
                ref_fasta = ref_fasta,
                ref_fai = ref_fai,
                ref_dict = ref_dict,
                tumor_reads = tumor_reads,
                tumor_reads_index = tumor_reads_index,
                normal_reads = normal_reads,
                normal_reads_index = normal_reads_index,
                normal_sample_name = normal_sample_name,
                tumor_sample_name = tumor_sample_name,
                pon = pon,
                pon_idx = pon_idx,
                gnomad = gnomad,
                gnomad_idx = gnomad_idx,
                m2_extra_args = m2_extra_args,
                make_bamout = make_bamout,
                compress_vcfs = compress_vcfs,
                runtime_params = standard_runtime,
                cooking_show_mode = cooking_show_mode
        }
    }

    call MergeVCFs {
        input:
            input_vcfs = M2.filtered_vcf,
            input_vcf_indices = M2.filtered_vcf_idx,
            output_name = "merged",
            compress = compress_vcfs,
            runtime_params = standard_runtime,
            cooking_show_mode = cooking_show_mode
    }

    call MergeVCFStats {
        input:
            stats_files = M2.stats_file,
            runtime_params = standard_runtime,
            cooking_show_mode = cooking_show_mode
    }

    call Filter {
        input:
            ref_fasta = ref_fasta,
            ref_fai = ref_fai,
            ref_dict = ref_dict,
            unfiltered_vcf = MergeVCFs.output_vcf,
            unfiltered_vcf_idx = MergeVCFs.output_vcf_idx,
            output_name = "filtered",
            compress = compress_vcfs,
            m2_extra_filtering_args = m2_extra_filtering_args,
            runtime_params = standard_runtime,
            mutect_stats = MergeVCFStats.merged_stats,
            cooking_show_mode = cooking_show_mode
    }

    if (vcf2maf) {
        call Vcf2Maf {
            input:
                input_vcf = Filter.filtered_vcf,
                maf_output = vcf2maf_output,
                runtime_params = standard_runtime,
                cooking_show_mode = cooking_show_mode
        }
    }

    output {
        File filtered_vcf = Filter.filtered_vcf
        File filtered_vcf_idx = Filter.filtered_vcf_idx
        File? maf_file = Vcf2Maf.maf_file
    }
}

task SplitIntervals {
    input {
        File? intervals
        File ref_fasta
        File ref_fai
        File ref_dict
        Int scatter_count
        String? split_intervals_extra_args
        Boolean cooking_show_mode = false
        Runtime runtime_params
    }

    command {
        echo "=== SplitIntervals Task ==="
        echo "Cooking show mode: ~{cooking_show_mode}"
        echo "Inputs:"
        echo "  ref_fasta: ~{ref_fasta}"
        echo "  intervals: ~{intervals}"
        echo "  scatter_count: ~{scatter_count}"

        if [ "~{cooking_show_mode}" = "true" ]; then
            echo "COOKING SHOW MODE: Creating ~{scatter_count} placeholder interval files"
            for i in $(seq 1 ~{scatter_count}); do
                echo "# Placeholder interval file $i" > $(printf "%04d" $i)-scattered.interval_list
            done
        else
            echo "PRODUCTION MODE: Running actual SplitIntervals"
            mkdir interval-files
            gatk --java-options "-Xmx~{runtime_params.command_mem}m" SplitIntervals \
                -R ~{ref_fasta} \
                ~{"-L " + intervals} \
                -scatter ~{scatter_count} \
                -O interval-files \
                ~{split_intervals_extra_args}
            cp interval-files/*.interval_list .
        fi
    }

    runtime {
        docker: runtime_params.gatk_docker
        memory: "~{runtime_params.machine_mem} MiB"
        cpu: runtime_params.cpu
    }

    output {
        Array[File] interval_files = glob("*.interval_list")
    }
}

task M2 {
    input {
        File intervals
        File ref_fasta
        File ref_fai
        File ref_dict
        File tumor_reads
        File tumor_reads_index
        File normal_reads
        File normal_reads_index
        String tumor_sample_name
        String normal_sample_name
        File? pon
        File? pon_idx
        File? gnomad
        File? gnomad_idx
        String? m2_extra_args
        Boolean make_bamout = false
        Boolean compress_vcfs = false
        Boolean cooking_show_mode = false
        Runtime runtime_params
    }

    String output_vcf = "output" + if compress_vcfs then ".vcf.gz" else ".vcf"
    String output_vcf_idx = output_vcf + if compress_vcfs then ".tbi" else ".idx"

    command {
        echo "=== M2 (Mutect2) Task ==="
        echo "Cooking show mode: ~{cooking_show_mode}"
        echo "Inputs:"
        echo "  intervals: ~{intervals}"
        echo "  tumor_reads: ~{tumor_reads}"
        echo "  normal_reads: ~{normal_reads}"
        echo "  pon: ~{pon}"
        echo "  gnomad: ~{gnomad}"

        if [ "~{cooking_show_mode}" = "true" ]; then
            echo "COOKING SHOW MODE: Creating placeholder VCF output"
            echo "##fileformat=VCFv4.2" > ~{output_vcf}
            echo "##source=CookingShowMode" >> ~{output_vcf}
            echo "#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO" >> ~{output_vcf}
            echo "chr1	1000	.	A	T	60	PASS	." >> ~{output_vcf}
            
            echo "# M2 Stats - Cooking Show Mode" > ~{output_vcf}.stats
            echo "sample_name	total_variants" >> ~{output_vcf}.stats
            echo "~{tumor_sample_name}	1" >> ~{output_vcf}.stats
            
            if [ "~{compress_vcfs}" = "true" ]; then
                bgzip ~{output_vcf}
                tabix -p vcf ~{output_vcf}.gz
            else
                touch ~{output_vcf_idx}
            fi
        else
            echo "PRODUCTION MODE: Running actual Mutect2"
            gatk --java-options "-Xmx~{runtime_params.command_mem}m" Mutect2 \
                -R ~{ref_fasta} \
                -I ~{tumor_reads} \
                -I ~{normal_reads} \
                -normal ~{normal_sample_name} \
                ~{"-pon " + pon} \
                ~{"--germline-resource " + gnomad} \
                -L ~{intervals} \
                -O ~{output_vcf} \
                ~{m2_extra_args}
        fi
    }

    runtime {
        docker: runtime_params.gatk_docker
        memory: "~{runtime_params.machine_mem} MiB"
        cpu: runtime_params.cpu
    }

    output {
        File filtered_vcf = output_vcf
        File filtered_vcf_idx = output_vcf_idx
        File stats_file = "~{output_vcf}.stats"
    }
}

task MergeVCFs {
    input {
        Array[File] input_vcfs
        Array[File] input_vcf_indices
        String output_name
        Boolean compress = false
        Boolean cooking_show_mode = false
        Runtime runtime_params
    }

    String output_vcf_name = output_name + if compress then ".vcf.gz" else ".vcf"
    String output_vcf_idx_name = output_vcf_name + if compress then ".tbi" else ".idx"

    command {
        echo "=== MergeVCFs Task ==="
        echo "Cooking show mode: ~{cooking_show_mode}"
        echo "Inputs: ${sep=' ' input_vcfs}"

        if [ "~{cooking_show_mode}" = "true" ]; then
            echo "COOKING SHOW MODE: Creating placeholder merged VCF"
            echo "##fileformat=VCFv4.2" > ~{output_vcf_name}
            echo "##source=CookingShowMode_Merged" >> ~{output_vcf_name}
            echo "#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO" >> ~{output_vcf_name}
            echo "chr1	1000	.	A	T	60	PASS	." >> ~{output_vcf_name}
            
            if [ "~{compress}" = "true" ]; then
                bgzip ~{output_vcf_name}
                tabix -p vcf ~{output_vcf_name}.gz
            else
                touch ~{output_vcf_idx_name}
            fi
        else
            echo "PRODUCTION MODE: Running actual MergeVcfs"
            gatk --java-options "-Xmx~{runtime_params.command_mem}m" MergeVcfs \
                -I ${sep=' -I ' input_vcfs} \
                -O ~{output_vcf_name}
        fi
    }

    runtime {
        docker: runtime_params.gatk_docker
        memory: "~{runtime_params.machine_mem} MiB"
        cpu: runtime_params.cpu
    }

    output {
        File output_vcf = output_vcf_name
        File output_vcf_idx = output_vcf_idx_name
    }
}

task Filter {
    input {
        File ref_fasta
        File ref_fai
        File ref_dict
        File unfiltered_vcf
        File unfiltered_vcf_idx
        String output_name
        Boolean compress = false
        String? m2_extra_filtering_args
        Boolean cooking_show_mode = false
        File? mutect_stats
        Runtime runtime_params
    }

    String output_vcf_name = output_name + if compress then ".vcf.gz" else ".vcf"
    String output_vcf_idx_name = output_vcf_name + if compress then ".tbi" else ".idx"

    command {
        echo "=== Filter Task ==="
        echo "Cooking show mode: ~{cooking_show_mode}"
        echo "Inputs:"
        echo "  unfiltered_vcf: ~{unfiltered_vcf}"
        echo "  ref_fasta: ~{ref_fasta}"

        if [ "~{cooking_show_mode}" = "true" ]; then
            echo "COOKING SHOW MODE: Creating placeholder filtered VCF"
            echo "##fileformat=VCFv4.2" > ~{output_vcf_name}
            echo "##source=CookingShowMode_Filtered" >> ~{output_vcf_name}
            echo "#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO" >> ~{output_vcf_name}
            echo "chr1	1000	.	A	T	60	PASS	." >> ~{output_vcf_name}
            
            if [ "~{compress}" = "true" ]; then
                bgzip ~{output_vcf_name}
                tabix -p vcf ~{output_vcf_name}.gz
            else
                touch ~{output_vcf_idx_name}
            fi
        else
            echo "PRODUCTION MODE: Running actual FilterMutectCalls"
            gatk --java-options "-Xmx~{runtime_params.command_mem}m" FilterMutectCalls \
                -R ~{ref_fasta} \
                -V ~{unfiltered_vcf} \
                ~{"-stats " + mutect_stats} \
                -O ~{output_vcf_name} \
                ~{m2_extra_filtering_args}
        fi
    }

    runtime {
        docker: runtime_params.gatk_docker
        memory: "~{runtime_params.machine_mem} MiB"
        cpu: runtime_params.cpu
    }

    output {
        File filtered_vcf = output_vcf_name
        File filtered_vcf_idx = output_vcf_idx_name
    }
}

task Vcf2Maf {
    input {
        File input_vcf
        File maf_output
        Boolean cooking_show_mode = false
        Runtime runtime_params
    }

    command {
        echo "=== Vcf2Maf Task ==="
        echo "Cooking show mode: ~{cooking_show_mode}"
        echo "Inputs:"
        echo "  input_vcf: ~{input_vcf}"
        echo "  maf_output: ~{maf_output}"

        if [ "~{cooking_show_mode}" = "true" ]; then
            echo "COOKING SHOW MODE: Using provided MAF file"
            cp ~{maf_output} output.maf
        else
            echo "PRODUCTION MODE: Would run vcf2maf conversion, but use mock instead"
            cp ~{maf_output} output.maf
        fi
    }

    runtime {
        docker: runtime_params.gatk_docker
        memory: "~{runtime_params.machine_mem} MiB"
        cpu: runtime_params.cpu
    }

    output {
        File maf_file = "output.maf"
    }
}

task MergeVCFStats {
    input {
        Array[File] stats_files
        String output_name = "merged_stats"
        Boolean cooking_show_mode = false
        Runtime runtime_params
    }

    command {
        echo "=== MergeVCFStats Task ==="
        echo "Cooking show mode: ~{cooking_show_mode}"
        echo "Input stats files: ${sep=' ' stats_files}"

        if [ "~{cooking_show_mode}" = "true" ]; then
            echo "COOKING SHOW MODE: Creating placeholder merged stats"
            echo "# Merged M2 Stats - Cooking Show Mode" > ~{output_name}.stats
            echo "sample_name\ttotal_variants\tfiltered_variants" >> ~{output_name}.stats
            echo "sample1\t100\t10" >> ~{output_name}.stats
        else
            echo "PRODUCTION MODE: Running actual MergeMutectStats"
            gatk --java-options "-Xmx~{runtime_params.command_mem}m" MergeMutectStats \
                ${sep=' ' prefix('-stats ', stats_files)} \
                -O ~{output_name}.stats
        fi
    }

    runtime {
        docker: runtime_params.gatk_docker
        memory: "~{runtime_params.machine_mem} MiB"
        cpu: runtime_params.cpu
    }

    output {
        File merged_stats = "~{output_name}.stats"
    }
}
